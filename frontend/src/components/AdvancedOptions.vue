<template>
  <div class="advanced-options">
    <el-form label-position="left" label-width="100px" size="small">
      <el-form-item :label="$t('options.formula')">
        <el-switch v-model="store.options.formulaEnable" />
      </el-form-item>

      <el-form-item :label="$t('options.table')">
        <el-switch v-model="store.options.tableEnable" />
      </el-form-item>

      <el-form-item :label="$t('options.forceOcr')">
        <el-switch v-model="store.options.isOcr" />
      </el-form-item>

      <el-form-item :label="$t('options.maxPages')">
        <el-slider v-model="store.options.maxPages" :max="99999" :min="1" show-input />
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { useAppStore } from '@/stores/app'

const store = useAppStore()
</script>

<style scoped>
.advanced-options {
  padding: 12px;
  background: #fff;
  border-radius: var(--mineru-radius);
  border: 1px solid var(--mineru-border);
}
</style>
