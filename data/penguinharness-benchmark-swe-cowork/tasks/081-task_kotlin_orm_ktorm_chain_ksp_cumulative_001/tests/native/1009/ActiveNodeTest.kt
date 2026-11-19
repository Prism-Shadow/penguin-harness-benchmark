package org.ktorm.bench

import com.tschuchort.compiletesting.*
import com.google.devtools.ksp.processing.SymbolProcessorProvider
import org.junit.Test
import kotlin.test.assertEquals

class ActiveNodeTest {
    private fun provider(): SymbolProcessorProvider =
        java.util.ServiceLoader.load(
            SymbolProcessorProvider::class.java, SymbolProcessorProvider::class.java.classLoader
        ).firstOrNull { it.javaClass.name == "org.ktorm.ksp.compiler.KtormProcessorProvider" }
            ?: throw AssertionError("KSP provider service is not available")

    @Test
    fun behavior() {
        val provider = provider()
        val source = SourceFile.kotlin("Source.kt", """
            import java.sql.*
            import java.time.*
            import java.util.*
            import kotlin.reflect.*
            import org.ktorm.database.*
            import org.ktorm.dsl.*
            import org.ktorm.entity.*
            import org.ktorm.ksp.annotation.*
@Table
            data class KeywordRow(
                @PrimaryKey var id: Int,
                var `class`: String,
                var operator: String
            )
            fun run() {
                check(KeywordRows.columns.map { it.name } == listOf("id", "class", "operator"))
                check(KeywordRows.`class`.sqlType.typeCode == java.sql.Types.VARCHAR)
            }
        """.trimIndent())
        val result = KotlinCompilation().apply {
            sources = listOf(source)
            inheritClassPath = true
            jvmTarget = "17"
            verbose = false
            allWarningsAsErrors = false
            symbolProcessorProviders = listOf(provider)
            kspIncremental = true
            kspWithCompilation = true
            kspArgs["ktorm.ktlintExecutable"] = System.getenv("KTORM_KTLINT") ?: "/opt/ktlint.jar"
        }.compile()
        assertEquals(KotlinCompilation.ExitCode.OK, result.exitCode, result.messages)
        result.classLoader.loadClass("SourceKt").getMethod("run").invoke(null)
    }
}
