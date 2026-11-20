package org.ktorm.bench

import org.junit.Test
import org.ktorm.entity.Entity
import org.ktorm.schema.Table
import org.ktorm.schema.int

class ActiveNodeTest {
    interface Loop : Entity<Loop> {
        val id: Int
        val loop: Loop
    }

    object Loops : Table<Loop>("loop") {
        val id = int("id").primaryKey().bindTo { it.id }
        val loopId = int("loop_id").references(Loops) { it.loop }
    }

    @Test
    fun behavior() {
        val thrown = runCatching { Loops.columns }.exceptionOrNull()
            ?: throw AssertionError("a self reference must be rejected")
        val cause = if (thrown is ExceptionInInitializerError) thrown.cause else thrown
        check(cause is IllegalStateException) { "unexpected failure: $cause" }
        check(cause.message == "Circular reference detected, current table: 'loop', reference route: loop") {
            "unexpected circular-reference message: ${cause.message}"
        }
    }
}
