package org.ktorm.bench

import com.google.devtools.ksp.processing.SymbolProcessorEnvironment
import com.google.devtools.ksp.processing.SymbolProcessorProvider
import com.google.devtools.ksp.processing.SymbolProcessor
import com.google.devtools.ksp.processing.Resolver
import com.google.devtools.ksp.symbol.KSAnnotated
import com.squareup.kotlinpoet.PropertySpec
import com.squareup.kotlinpoet.TypeSpec
import com.tschuchort.compiletesting.*
import org.junit.Test
import org.ktorm.ksp.spi.ExtCodeGenerator
import org.ktorm.ksp.spi.TableMetadata
import kotlin.test.assertEquals

public class BenchExtCodeGenerator : ExtCodeGenerator {
    override fun generateTypes(
        table: TableMetadata,
        environment: SymbolProcessorEnvironment
    ): List<TypeSpec> {
        check(runCatching {
            Thread.currentThread().contextClassLoader.loadClass(javaClass.name)
        }.isFailure)
        return listOf(TypeSpec.classBuilder("TestFor" + table.tableClassName)
            .addProperty(PropertySpec.builder("originName", String::class)
                .initializer("%S", table.name).build())
            .build())
    }
}

class ActiveNodeTest {
    private fun <Result> isolated(action: () -> Result): Result {
        val oldLoader = Thread.currentThread().contextClassLoader
        try {
            Thread.currentThread().contextClassLoader = object : ClassLoader(null) {}
            return action()
        } finally {
            Thread.currentThread().contextClassLoader = oldLoader
        }
    }

    @Test
    fun behavior() {
        val provider = isolated {
            Class.forName("org.ktorm.ksp.compiler.KtormProcessorProvider")
                .getDeclaredConstructor().newInstance() as SymbolProcessorProvider
        }
        val isolatedProvider = object : SymbolProcessorProvider {
            override fun create(environment: SymbolProcessorEnvironment): SymbolProcessor {
                val delegate = isolated { provider.create(environment) }
                return object : SymbolProcessor {
                    override fun process(resolver: Resolver): List<KSAnnotated> = isolated { delegate.process(resolver) }
                    override fun finish() = isolated { delegate.finish() }
                    override fun onError() = isolated { delegate.onError() }
                }
            }
        }

        val source = SourceFile.kotlin("Source.kt", """
            import org.ktorm.ksp.annotation.*
            @Table data class User(@PrimaryKey var id: Int, var name: String)
            @Table(name = "audit_entry") data class Event(@PrimaryKey var id: Int)
            class Plain
            fun run() {
                check(TestForUsers().originName == "user")
                check(TestForEvents().originName == "audit_entry")
                check(runCatching { Class.forName("TestForPlains") }.isFailure)
            }
        """.trimIndent())
        val result = KotlinCompilation().apply {
            sources = listOf(source)
            inheritClassPath = true
            jvmTarget = "17"
            symbolProcessorProviders = listOf(isolatedProvider)
            kspIncremental = true
            kspWithCompilation = true
            kspArgs["ktorm.ktlintExecutable"] = System.getenv("KTORM_KTLINT") ?: "/opt/ktlint.jar"
        }.compile()
        assertEquals(KotlinCompilation.ExitCode.OK, result.exitCode, result.messages)
        result.classLoader.loadClass("SourceKt").getMethod("run").invoke(null)
    }
}
