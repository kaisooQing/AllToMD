<template>
  <aside class="history-panel">
    <div class="history-header">
      <span class="title">{{ $t('history.title') }}</span>
      <el-button
        v-if="store.history.length"
        size="small"
        link
        @click="store.clearHistory"
      >
        {{ $t('history.clear') }}
      </el-button>
    </div>

    <div class="history-list">
      <div v-if="!store.history.length" class="empty">
        {{ $t('history.empty') }}
      </div>
      <div
        v-for="item in store.history"
        :key="item.id"
        class="history-item"
        :class="{ active: item.taskId === store.currentTaskId }"
        role="button"
        tabindex="0"
        title="点击恢复转换结果"
        @click="loadHistoryItem(item)"
        @keydown.enter="loadHistoryItem(item)"
      >
        <el-icon class="file-icon" :class="`file-icon-${getFileKind(item.name, item.taskId)}`">
          <component :is="getHistoryIcon(item.name, item.taskId)" />
        </el-icon>
        <div class="item-info">
          <div class="item-name" :title="item.name">{{ item.name }}</div>
          <div class="item-meta">
            <span>{{ formatTime(item.timestamp) }}</span>
            <span class="type-badge">{{ getFileTypeLabel(item.name, item.taskId) }}</span>
            <span v-if="item.hasImages" class="has-img">IMG</span>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { DataAnalysis, Document, Files, Grid, Link, Picture, Tickets } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { getFileKind, getFileTypeLabel } from '@/utils/fileType'

const store = useAppStore()

function formatTime(ts) {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

function getHistoryIcon(name, taskId) {
  const iconMap = {
    excel: Grid,
    word: Document,
    ppt: DataAnalysis,
    pdf: Tickets,
    image: Picture,
    html: Link,
    url: Link,
    markdown: Document,
    json: Files,
    file: Files,
  }
  return iconMap[getFileKind(name, taskId)] || Files
}

async function loadHistoryItem(item) {
  store.loadHistoryItem(item)
  if (!item.mdContent && !item.txtContent) {
    ElMessage.info('这条旧历史记录只保存了目录信息，请重新转换一次后即可点击恢复完整结果')
  }
}
</script>

<style scoped>
.history-panel {
  width: var(--mineru-sidebar-width);
  min-width: var(--mineru-sidebar-width);
  background: #fff;
  border-right: 1px solid var(--mineru-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--mineru-border);
}

.title {
  font-weight: 700;
  font-size: 14px;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.empty {
  color: var(--mineru-text-tertiary);
  text-align: center;
  padding: 24px 0;
  font-size: 12px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: var(--mineru-radius-sm);
  cursor: pointer;
  transition: background 0.15s;
}

.history-item:hover,
.history-item.active {
  background: var(--mineru-accent-soft);
}

.file-icon {
  color: var(--mineru-accent);
  font-size: 18px;
  flex: none;
}

.item-info {
  min-width: 0;
  flex: 1;
}

.item-name {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: var(--mineru-text-tertiary);
  margin-top: 2px;
}

.has-img {
  color: var(--mineru-accent);
  font-weight: 600;
}

.type-badge {
  color: var(--mineru-text-secondary);
  font-weight: 600;
}

.file-icon-excel {
  color: #16a34a;
}

.file-icon-word {
  color: #2563eb;
}

.file-icon-ppt {
  color: #ea580c;
}

.file-icon-pdf {
  color: #dc2626;
}

.file-icon-image {
  color: #7c3aed;
}

.file-icon-html,
.file-icon-url {
  color: #0891b2;
}
</style>
