package org.ktorm.bench

import org.junit.Test
import kotlin.test.assertEquals
import org.ktorm.schema.*
import java.sql.Types

class ActiveNodeTest {
    @Test
    fun behavior() {

        check(SqlType.of<Int>() === IntSqlType)
        check(SqlType.of<String>() === VarcharSqlType)
        
    }
}
