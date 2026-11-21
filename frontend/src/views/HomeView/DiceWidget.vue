<script setup lang="ts">
/**
 * DiceWidget – a simple dice-rolling widget supporting W4, W6, W8, W12, and W20.
 */
import { ref } from 'vue'
import { useSessionStore } from '@/stores/session.ts'

const store = useSessionStore()

/** Dice */
const diceResult = ref<string>('')

/** Dice */
function rollDice(sides: number) {
  const result = Math.floor(Math.random() * sides) + 1
  diceResult.value = `W${sides} → ${result}`
}
</script>

<template>
  <div :class="['dice-widget', 'rail-panel', !store.isLeader ? 'dice-widget--member' : null]">
    <h2 class="rail-title">Roll a dice</h2>
    <div class="dice-buttons">
      <button @click="rollDice(4)" class="dice-button submit-button">W4</button>
      <button @click="rollDice(6)" class="dice-button submit-button">W6</button>
      <button @click="rollDice(8)" class="dice-button submit-button">W8</button>
      <button @click="rollDice(12)" class="dice-button submit-button">W12</button>
      <button @click="rollDice(20)" class="dice-button submit-button">W20</button>
    </div>
    <div class="dice-result" v-if="diceResult">
      {{ diceResult }}
    </div>
  </div>
</template>

<style scoped>
/* Dice */
.dice-widget {
  position: static;
  width: 100%;
  margin-top: 0rem;
}

.dice-widget--member {
  margin-top: -20px;
}

/*
 * A fixed 3-column grid. With `flex: 1 0 30%` the trailing row stretched its
 * two buttons to fill the width, so W12/W20 rendered much wider than W4/W6/W8.
 */
.dice-buttons {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--dm-space-2);
}

.dice-button {
  margin-bottom: 0;
  padding: var(--dm-space-3);
  font-size: 1.15rem;
  text-align: center;
}

.dice-result {
  margin-top: var(--dm-space-4);
  text-align: center;
  font-weight: bold;
}
</style>
