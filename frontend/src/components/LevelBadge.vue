<template>
  <span class="px-1.5 py-0.5 rounded text-[11px] font-bold"
    :class="{
      'bg-red-900/70 text-red-300': level === 'critical',
      'bg-yellow-900/60 text-yellow-300': level === 'warning',
      'bg-blue-900/60 text-blue-300': level === 'info',
    }">{{ level }}</span>
</template>

<script setup lang="ts">
import type { AlarmLevel } from '../types'
defineProps<{ level: AlarmLevel }>()
</script>
