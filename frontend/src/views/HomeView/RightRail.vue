<script setup lang="ts">
/**
 * RightRail – the right-hand sidebar containing the join link,
 * dice widget, and abilities/health section.
 */
import { useSessionStore } from '@/stores/session.ts'
import DiceWidget from '../HomeView/DiceWidget.vue'
import AbilitiesSection from '../HomeView/AbilitiesSection.vue'
import JoinLink from '@/views/HomeView/JoinLink.vue'

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

<style scoped>
/*
 * Right rail layout.
 *
 * The rail is a real grid column in `HomeView`'s `.container` and sticks below
 * the fixed header while the main column scrolls. It previously used
 * `position: fixed; right: 15%`, which took it out of the flow and let it
 * overlap the main content once the content was no longer pinned to the left
 * half of the screen by the global starter grid.
 */
.right-rail {
  position: sticky;
  top: 60px;
  width: 100%;
  max-height: calc(100vh - 70px);
  box-sizing: border-box;
  color: var(--dm-ink);
  font-family: var(--dm-font-display);
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.right-rail::-webkit-scrollbar {
  display: none;
}

.right-rail--leader,
.right-rail--member {
  padding-right: var(--dm-space-2);
}

/* Cards stacked with even spacing. The offset aligns the first card with
   `.centered-content`, which clears the fixed header. */
.right-rail__inner {
  margin-top: 60px;
  display: flex;
  flex-direction: column;
  gap: var(--dm-space-6);
}

/* Responsive design – the rail becomes a normal block under the content. */
@media (max-width: 1300px) {
  .right-rail {
    position: static;
    max-height: none;
    padding-right: 0;
  }

  .right-rail--leader,
  .right-rail--member {
    overflow: visible;
  }

  .right-rail__inner {
    margin-top: var(--dm-space-5);
  }
}
</style>
