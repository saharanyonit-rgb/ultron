package com.ultron.ai

import com.google.gson.JsonObject
import com.ultron.ai.data.model.CoreState
import com.ultron.ai.data.model.JarvisEvent
import com.ultron.ai.data.model.PendingPermissionRequest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class SseClientTest {

    @Test
    fun testPermissionRequiredEventMapping() {
        val event = JarvisEvent("permission_required", null)
        assertEquals(CoreState.PERMISSION_REQUIRED, event.coreTransition())
    }

    @Test
    fun testPermissionRequiredJsonParsing() {
        val data = JsonObject().apply {
            addProperty("permission_id", "perm_123456")
            addProperty("tool", "execute_command")
            addProperty("risk", "high")
            addProperty("reason", "Command execution requires confirmation")
            val args = JsonObject().apply {
                addProperty("command", "dir")
            }
            add("arguments", args)
        }
        val request = PendingPermissionRequest.fromJson(data)
        assertNotNull(request)
        assertEquals("perm_123456", request?.permissionId)
        assertEquals("execute_command", request?.tool)
        assertEquals("high", request?.risk)
        assertEquals("Command execution requires confirmation", request?.reason)
        assertEquals("\"dir\"", request?.arguments?.get("command"))
    }

    @Test
    fun testCoreTransitions() {
        assertEquals(CoreState.THINKING, JarvisEvent("planning", null).coreTransition())
        assertEquals(CoreState.CONNECTED, JarvisEvent("completed", null).coreTransition())
        assertEquals(CoreState.CONNECTED, JarvisEvent("permission_decided", null).coreTransition())
        assertEquals(CoreState.ERROR, JarvisEvent("failed", null).coreTransition())
    }
}
