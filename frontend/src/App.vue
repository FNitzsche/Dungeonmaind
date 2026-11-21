<!-- App root component – the single-page application shell. -->
<script setup lang="ts">
import { usePlayerPresence } from '@/composables/usePlayerPresence'

usePlayerPresence()
</script>

<template>
  <div>
    <router-view />
  </div>
</template>
