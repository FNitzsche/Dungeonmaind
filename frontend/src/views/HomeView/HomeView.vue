<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useSessionStore } from '@/stores/session.ts'

import HomeHeader from '@/views/HomeView/HomeHeader.vue'
import SessionOverview from '@/views/HomeView/SessionOverview.vue'
import QuestionSection from '@/views/HomeView/QuestionSection.vue'
import RecordingSection from '@/views/HomeView/RecordingSection.vue'
import AudioUploadSection from '@/views/HomeView/AudioUploadSection.vue'
import RightRail from '@/views/HomeView/RightRail.vue'

const router = useRouter()
const store = useSessionStore()

onMounted(async () => {
  /*
   * If no player session exists, return to login.
   */
  if (!store.currentPlayer) {
    await router.push({
      name: 'login',
    })

    return
  }

  /*
   * The WebSocket is managed by the session store.
   * It remains connected when navigating between
   * Home and Timeline.
   */
  await store.connectPlayerSocket()

  /*
   * Refresh the visible player list after returning
   * from another page such as the Timeline.
   */
  try {
    await store.loadPlayers()
  } catch (error) {
    console.error(
      'Failed to load players:',
      error,
    )
  }
})
</script>

<template>
  <div class="home-page">
    <HomeHeader />

    <main class="home-layout">
      <section class="centered-content">
        <SessionOverview />

        <QuestionSection />

        <hr
          v-if="store.isLeader"
          style="margin: 2rem 0"
        />

        <RecordingSection
          v-if="store.isLeader"
        />

        <hr
          v-if="store.isLeader"
          style="margin: 2rem 0"
        />

        <AudioUploadSection
          v-if="store.isLeader"
        />
      </section>

      <RightRail />
    </main>
  </div>
</template>

<style src="@/assets/styles.css"></style>

<style scoped>
.home-page {
  width: 100%;
  min-height: 100vh;
  box-sizing: border-box;
}

.home-layout {
  display: grid;
  grid-template-columns:
    minmax(0, 600px)
    minmax(360px, 540px);
  justify-content: center;
  align-items: start;
  gap: 2rem;

  width: min(1180px, calc(100% - 2rem));
  margin: 0 auto;
  padding: 7rem 1rem 2rem;
  box-sizing: border-box;
}

.centered-content {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 2rem;

  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  background-color: rgba(163, 148, 95, 0.8);
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
}

@media (max-width: 1100px) {
  .home-layout {
    width: min(700px, calc(100% - 1rem));
    grid-template-columns: 1fr;
    gap: 1.5rem;
    padding-top: 7rem;
  }
}

@media (max-width: 600px) {
  .home-layout {
    width: 100%;
    padding: 6.5rem 0.5rem 1rem;
  }

  .centered-content {
    padding: 1rem;
  }
}
</style>