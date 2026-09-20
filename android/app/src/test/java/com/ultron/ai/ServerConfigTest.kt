package com.ultron.ai

import com.ultron.ai.data.model.ServerConfig
import com.ultron.ai.data.model.ServerMode
import org.junit.Assert.assertEquals
import org.junit.Test

class ServerConfigTest {

    @Test
    fun testLoopbackConfig() {
        val config = ServerConfig(mode = ServerMode.LOOPBACK, address = "127.0.0.1", port = 8080)
        assertEquals("http://127.0.0.1:8080", config.baseUrl)
        assertEquals("http://127.0.0.1:8080", config.displayUrl())
    }

    @Test
    fun testRemoteHttpsConfig() {
        val config = ServerConfig(mode = ServerMode.REMOTE, address = "192.168.1.100", port = 8080, useHttps = true)
        assertEquals("https://192.168.1.100:8080", config.baseUrl)
        assertEquals("https", config.scheme)
    }
}
