<script setup lang="ts">
import { useSessionStore } from '@/stores/session.ts'
import DiceWidget from '../HomeView/DiceWidget.vue'
import AbilitiesSection from '../HomeView/AbilitiesSection.vue'
import JoinLink from "@/views/HomeView/JoinLink.vue";

const store = useSessionStore()
</script>

<template>
  <!-- Right: abilities, health and dice -->
  <aside :class="['right-rail', store.isLeader ? 'right-rail--leader' : 'right-rail--member']">
    <div :class="['right-rail__inner', store.isLeader ? 'right-rail__inner--leader' : null]">
      <JoinLink />
      <DiceWidget />
      <AbilitiesSection />
    </div>
  </aside>
</template>

<style src="@/assets/styles.css"></style>
<style scoped>
/* Right rail layout */
.right-rail {
  position: static;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  color: #392401;
  font-family: 'MedievalSharp', cursive;
  overflow: visible;
}

.right-rail__inner {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  padding-top: 0;
}

.right-rail__inner--leader {
  padding-top: 0;
}

@media (max-width: 1100px) {
  .right-rail__inner,
  .right-rail__inner--leader {
    padding-top: 0;
  }
}
</style>
