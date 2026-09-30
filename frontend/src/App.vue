<template>
  <div class="app-root">
    <AppHeader />
    <main class="workspace">
      <HistoryPanel />
      <UploadPanel />
      <ResultPanel />
    </main>
  </div>
</template>

<script setup>
import AppHeader from './components/AppHeader.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import UploadPanel from './components/UploadPanel.vue'
import ResultPanel from './components/ResultPanel.vue'
</script>

<style scoped>
.app-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.workspace {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}
</style>
