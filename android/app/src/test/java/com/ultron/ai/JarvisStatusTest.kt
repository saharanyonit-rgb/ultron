package com.ultron.ai

import com.google.gson.JsonObject
import com.ultron.ai.data.model.JarvisStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class JarvisStatusTest {

    @Test
    fun testStatusMappingRunning() {
        val json = JsonObject().apply {
            addProperty("status", "running")
            addProperty("server", "JARVIS API")
            addProperty("version", "2.0.0")
        }
        val status = JarvisStatus.fromJson(json)
        assert(status != null)
        assertEquals("running", status?.status)
        assertTrue("running status should be mapped to isOnline = true", status!!.isOnline)
    }

    @Test
    fun testStatusMappingOnline() {
        val status = JarvisStatus("online", "JARVIS", "2.0.0", null)
        assertTrue(status.isOnline)
    }

    @Test
    fun testStatusMappingReadyAndHealthy() {
        val readyStatus = JarvisStatus("ready", "JARVIS", "2.0.0", null)
        val healthyStatus = JarvisStatus("healthy", "JARVIS", "2.0.0", null)
        assertTrue(readyStatus.isOnline)
        assertTrue(healthyStatus.isOnline)
    }

    @Test
    fun testStatusMappingOfflineAndError() {
        val offlineStatus = JarvisStatus("offline", "JARVIS", "2.0.0", null)
        val errorStatus = JarvisStatus("error", "JARVIS", "2.0.0", null)
        assertFalse(offlineStatus.isOnline)
        assertFalse(errorStatus.isOnline)
    }
}
