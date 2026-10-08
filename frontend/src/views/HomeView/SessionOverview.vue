<script setup lang="ts">
/**
 * SessionOverview – displays a greeting with the current player's name.
 */
import { useSessionStore } from '@/stores/session.ts'

const store = useSessionStore()
</script>

<template>
  <section>
    <h2 class="hello-title">Hello {{ store.currentPlayer?.name }}</h2>
  </section>
</template>

<style src="@/assets/styles.css"></style>
<style scoped>
.hello-title {
  font-size: 1.9rem;
  line-height: 1.15;
  margin: 0 0 0.5rem 0;
  font-family: 'MedievalSharp', cursive;
  font-weight: 800;
}
</style>
