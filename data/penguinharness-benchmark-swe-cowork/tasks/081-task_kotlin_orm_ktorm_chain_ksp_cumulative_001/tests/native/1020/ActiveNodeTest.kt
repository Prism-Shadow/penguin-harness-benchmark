package org.ktorm.bench

import java.net.URISyntaxException
import java.sql.DriverManager
import org.junit.Test
import org.ktorm.database.CachedRowSet

class ActiveNodeTest {
    @Test
    fun behavior() {
        DriverManager.getConnection("jdbc:h2:mem:cached_url_probe;DB_CLOSE_DELAY=-1").use { connection ->
            connection.createStatement().use { statement ->
                statement.executeQuery("select 'http://example.com/a b' as link").use { resultSet ->
                    val rows = CachedRowSet(resultSet)
                    check(rows.next())
                    val failure = runCatching { rows.getURL("link") }.exceptionOrNull()
                    check(failure is URISyntaxException) {
                        "invalid URI text must be rejected by URI parsing, but was: $failure"
                    }
                }
            }
        }
    }
}
