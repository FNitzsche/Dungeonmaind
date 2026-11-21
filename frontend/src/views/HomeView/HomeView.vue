<script setup lang="ts">
/**
 * HomeView – the main game dashboard. Renders questions, recording,
 * audio upload, and the right rail (dice, abilities, join link).
 * Player presence stays open in App.vue so Map/Timeline keep the socket.
 */
import { onMounted } from 'vue'
import { useSessionStore } from '@/stores/session.ts'
import { useRouter } from 'vue-router'
import HomeHeader from '@/views/HomeView/HomeHeader.vue'
import SessionOverview from '@/views/HomeView/SessionOverview.vue'
import QuestionSection from '@/views/HomeView/QuestionSection.vue'
import RecordingSection from '@/views/HomeView/RecordingSection.vue'
import AudioUploadSection from '@/views/HomeView/AudioUploadSection.vue'
import RightRail from '@/views/HomeView/RightRail.vue'

const router = useRouter()
const store = useSessionStore()

onMounted(() => {
  if (!store.currentPlayer) {
    void router.push({ name: 'login' })
  }
})
</script>

<template>
  <div class="container">
    <HomeHeader />

    <div class="centered-content">
      <SessionOverview />

      <!-- Left: main LLM -->
      <QuestionSection />

      <hr style="margin: 2rem 0" v-if="store.isLeader" />

      <!-- Leader-only: recording -->
      <RecordingSection v-if="store.isLeader" />

      <hr style="margin: 2rem 0" v-if="store.isLeader" />

      <!-- Leader-only: upload -->
      <AudioUploadSection v-if="store.isLeader" />
    </div>

    <RightRail />
  </div>
</template>

<style scoped>
/*
 * Dashboard layout.
 *
 * Two real columns: the main content stack and the right rail. This used to
 * depend on the global `#app` starter grid to push the content leftwards,
 * while the rail escaped the flow with `position: fixed; right: 15%`. The
 * columns are now declared here, so the two can never overlap.
 *
 * `.header` is `position: fixed`, so it is not a grid item.
 */
.container {
  display: grid;
  grid-template-columns: minmax(0, 600px) minmax(0, 540px);
  justify-content: center;
  align-items: start;
  gap: var(--dm-space-6);
  max-width: 1220px;
  margin: var(--dm-space-6) auto;
  padding: var(--dm-space-4);
  position: relative;
}

/* Centered content */
.centered-content {
  background-color: rgba(163, 148, 95, 0.8);
  padding: var(--dm-space-6);
  border-radius: var(--dm-radius-sm);
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
  margin-top: 60px;
}

/* Responsive design – collapse to a single column. */
@media (max-width: 1300px) {
  .container {
    grid-template-columns: minmax(0, 600px);
    max-width: 100%;
    margin: var(--dm-space-4) auto;
  }
}
</style>
