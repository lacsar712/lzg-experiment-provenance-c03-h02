<template>
  <div class="page">
    <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap">
      <div>
        <h1 style="margin-bottom: 4px">事件时间线</h1>
        <p class="muted" style="margin-top: 0">按 version 展示 event_store 原始事件</p>
      </div>
      <div style="display: flex; gap: 8px">
        <n-button @click="$router.push(`/runs/${id}`)">返回详情</n-button>
        <n-button @click="$router.push(`/runs/${id}/lineage`)">血缘</n-button>
      </div>
    </div>

    <div class="card">
      <n-timeline v-if="events.length">
        <n-timeline-item
          v-for="ev in events"
          :key="ev.id"
          :type="itemType(ev.event_type)"
          :title="`v${ev.version} · ${ev.event_type}`"
          :time="formatTime(ev.occurred_at)"
        >
          <div class="muted" style="margin-bottom: 6px">actor: {{ ev.actor }}</div>
          <pre class="mono" style="white-space: pre-wrap; margin: 0; font-size: 12px">{{
            JSON.stringify(ev.payload_json, null, 2)
          }}</pre>
        </n-timeline-item>
      </n-timeline>
      <n-spin v-else :show="loading" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { getEvents } from '../api/client'

const route = useRoute()
const message = useMessage()
const events = ref([])
const loading = ref(true)
const id = computed(() => route.params.id)

function formatTime(v) {
  return new Date(v).toLocaleString()
}

function itemType(t) {
  if (t === 'RunCompleted') return 'success'
  if (t === 'RunAborted') return 'warning'
  if (t === 'RunStarted') return 'info'
  return 'default'
}

onMounted(async () => {
  try {
    events.value = await getEvents(id.value)
  } catch (e) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
})
</script>
