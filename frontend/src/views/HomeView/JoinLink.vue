<script setup lang="ts">
/**
 * JoinLink – displays the local network join URL for other players
 * and a QR code modal for easy sharing (leader-only).
 */
import QrcodeVue from 'qrcode.vue'
import { SERVER_CONFIG } from '@/config/config'
import { useSessionStore } from '@/stores/session.ts'
import { ref } from 'vue'

const store = useSessionStore()
const localNetworkIP = SERVER_CONFIG.LOCAL_NETWORK_IP
const port = window.location.port
const showQRCodeModal = ref(false)
</script>

<template>
  <div v-if="store.isLeader" :class="['join-link', 'rail-panel']">
    <h2 class="rail-title">Join Link (New Members)</h2>
    <div v-if="localNetworkIP">
      <label>http://{{ localNetworkIP }}:{{ port }}</label>
      <button class="submit-button" @click="showQRCodeModal = true">QR Code</button>
      <p>
        Copy the join link or click the button to open<br />
        Dungeonmaind on another device via QR code
      </p>

      <div v-if="localNetworkIP && showQRCodeModal" class="modal-overlay">
        <div class="modal">
          <qrcode-vue :value="`http://${localNetworkIP}:${port}`" :size="180" level="M" />
          <p>
            Scan the code to open<br />
            Dungeonmaind on another device
          </p>
          <button class="submit-button" @click="showQRCodeModal = false">Done</button>
        </div>
      </div>
    </div>

    <div v-else>
      <p>
        No local network IP set<br />
        Please leave the session and rejoin as<br />
        Leader to set your local network IP
      </p>
    </div>
  </div>
</template>

<style src="@/assets/styles.css"></style>
<style scoped>
.join-link {
  font-family: 'MedievalSharp', cursive;
  font-weight: 600;
  font-size: 1.2rem;
  text-align: center;
}

label {
  font-weight: 600;
  font-size: 1.1rem;
  font-family: 'MedievalSharp', cursive;
  display: block;
  margin-bottom: 0.5rem;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.modal {
  background: rgba(163, 148, 95, 0.8);
  border-radius: 12px;
  padding: 24px;
  width: 340px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  text-align: center;
  color: #000;
}
</style>
