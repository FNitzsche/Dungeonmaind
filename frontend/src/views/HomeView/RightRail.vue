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

<style src="@/assets/styles.css"></style>
<style scoped>
/* Right rail layout */
.right-rail {
  position: fixed;
  right: 15%;
  width: 540px;
  z-index: 900;
  box-sizing: border-box;
  color: #392401;
  font-family: 'MedievalSharp', cursive;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.right-rail::-webkit-scrollbar {
  display: none;
}

/* Leader-Version: füllt vertikal den Bildschirmbereich */
.right-rail--leader {
  top: 60px;
  bottom: 5px;
  padding-right: 0.5rem;
}

/* Player-Version: fixed */
.right-rail--member {
  top: 60px;
  bottom: 5px;
  padding-right: 0.5rem;
}

/* Gemeinsames Layout innen: Cards untereinander mit Abstand */
.right-rail__inner {
  padding-top: 100px;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

/* Nur Leader: künstlicher Offset nach unten, damit die Box optisch nicht direkt unter dem Header klebt */
.right-rail__inner--leader {
  padding-top: 80px;
}

/* Responsive design */
@media (max-width: 1300px) {
  .right-rail {
    position: static;
    right: auto;
    top: auto;
    bottom: auto;
    width: auto;
    padding-right: 0;
  }

  .right-rail--leader,
  .right-rail--member {
    overflow: visible;
  }

  .right-rail__inner {
    padding-top: 60px;
  }

  .right-rail__inner--leader {
    padding-top: 20px;
  }
}
</style>
