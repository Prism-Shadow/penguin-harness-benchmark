package org.ktorm.bench

import com.google.devtools.ksp.processing.SymbolProcessorProvider
import com.google.devtools.ksp.symbol.KSClassDeclaration
import com.google.devtools.ksp.symbol.KSPropertyDeclaration
import com.tschuchort.compiletesting.*
import org.junit.Test
import org.ktorm.ksp.spi.CodingNamingStrategy
import org.ktorm.ksp.spi.TableMetadata
import kotlin.test.assertEquals

public open class BaseNaming : CodingNamingStrategy {
    override fun getTableClassName(c: KSClassDeclaration): String = c.simpleName.asString() + "Table"
    override fun getEntitySequenceName(c: KSClassDeclaration): String = "seq" + c.simpleName.asString()
    override fun getColumnPropertyName(c: KSClassDeclaration, prop: KSPropertyDeclaration): String =
        prop.simpleName.asString()
    override fun getRefColumnPropertyName(
        c: KSClassDeclaration, prop: KSPropertyDeclaration, ref: TableMetadata
    ): String = prop.simpleName.asString() + "Id"
}

public open class LegacyNaming : BaseNaming() {
    override fun getRefColumnPropertyNameForRefs(
        c: KSClassDeclaration, prop: KSPropertyDeclaration, ref: TableMetadata
    ): String = "legacy" + prop.simpleName.asString()
}

public class ModernNaming : BaseNaming() {
    override fun getRefTablePropertyName(
        c: KSClassDeclaration, prop: KSPropertyDeclaration, ref: TableMetadata
    ): String = "modern" + prop.simpleName.asString()
}

public class BothNaming : LegacyNaming() {
    override fun getRefTablePropertyName(
        c: KSClassDeclaration, prop: KSPropertyDeclaration, ref: TableMetadata
    ): String = "modern" + prop.simpleName.asString()
}

class ActiveNodeTest {
    private fun compile(code: String, strategy: String? = null): KotlinCompilation.Result =
        KotlinCompilation().apply {
            sources = listOf(SourceFile.kotlin("Source.kt", """
                import org.ktorm.entity.*
                import org.ktorm.ksp.annotation.*
                @Table interface Department : Entity<Department> { @PrimaryKey var id: Int }
                $code
            """.trimIndent()))
            inheritClassPath = true
            jvmTarget = "17"
            symbolProcessorProviders = listOf(
                Class.forName("org.ktorm.ksp.compiler.KtormProcessorProvider")
                    .getDeclaredConstructor().newInstance() as SymbolProcessorProvider
            )
            kspWithCompilation = true
            kspIncremental = true
            kspArgs["ktorm.ktlintExecutable"] = System.getenv("KTORM_KTLINT") ?: "/opt/ktlint.jar"
            if (strategy != null) kspArgs["ktorm.codingNamingStrategy"] = strategy
        }.compile()

    private fun run(result: KotlinCompilation.Result) {
        assertEquals(KotlinCompilation.ExitCode.OK, result.exitCode, result.messages)
        result.classLoader.loadClass("SourceKt").getMethod("run").invoke(null)
    }

    @Test
    fun annotationAliasesAndPrecedence() {
        run(compile("""
            @Table(className = "LegacyTable") interface Legacy : Entity<Legacy> {
                @PrimaryKey var id: Int
                @References(propertyNameForRefs = "oldDepartment") var department: Department
            }
            @Table(className = "ModernTable") interface Modern : Entity<Modern> {
                @PrimaryKey var id: Int
                @References(refTablePropertyName = "newDepartment") var department: Department
            }
            @Table(className = "MixedTable") interface Mixed : Entity<Mixed> {
                @PrimaryKey var id: Int
                @References(propertyNameForRefs = "discarded", refTablePropertyName = "preferred")
                var department: Department
            }
            @Table(className = "DefaultTable") interface Defaulted : Entity<Defaulted> {
                @PrimaryKey var id: Int
                @References(propertyNameForRefs = "", refTablePropertyName = "") var department: Department
            }
            fun run() {
                check(LegacyTable.refs.oldDepartment.tableName == "department")
                check(ModernTable.refs.newDepartment.tableName == "department")
                check(MixedTable.refs.preferred.tableName == "department")
                check(DefaultTable.refs.department.tableName == "department")
                check(MixedTable.refs.toList().single() === MixedTable.refs.preferred)
            }
        """.trimIndent()))
    }

    @Test
    fun strategiesHonorOldAndNewCallbacks() {
        val strategies = listOf(
            LegacyNaming::class.java.name to "legacy",
            ModernNaming::class.java.name to "modern",
            BothNaming::class.java.name to "modern"
        )
        for ((strategy, prefix) in strategies) {
            run(compile("""
                @Table interface Member : Entity<Member> {
                    @PrimaryKey var id: Int
                    @References var department: Department
                    @References var backup: Department
                }
                fun run() {
                    check(MemberTable.refs.${prefix}department.tableName == "department")
                    check(MemberTable.refs.${prefix}backup.tableName == "department")
                }
            """.trimIndent(), strategy))
        }
    }

    @Test
    fun losingAliasIsNotGenerated() {
        val result = compile("""
            @Table interface Member : Entity<Member> {
                @PrimaryKey var id: Int
                @References(propertyNameForRefs = "discarded", refTablePropertyName = "preferred")
                var department: Department
            }
            fun run() { Members.refs.discarded }
        """.trimIndent())
        assertEquals(KotlinCompilation.ExitCode.COMPILATION_ERROR, result.exitCode, result.messages)
        check(result.messages.contains("Unresolved reference: discarded")) { result.messages }
    }
}
