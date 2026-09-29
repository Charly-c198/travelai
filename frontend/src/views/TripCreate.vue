<template>
  <div class="trip-create-page">
    <div class="page-header"><h1>🗺️ 创建行程</h1></div>
    <a-card class="form-card" :bordered="false">
      <a-form :model="form" layout="vertical" @submit="handleSubmit">
        <a-form-item field="destination" label="目的地" :rules="[{ required: true, message: '请输入目的地' }]">
          <a-input v-model="form.destination" placeholder="例如：丽江、大理" allow-clear />
        </a-form-item>

        <a-form-item field="start_date" label="出发日期" :rules="[{ required: true, message: '请选择日期' }]">
          <a-date-picker v-model="form.start_date" style="width: 100%" placeholder="选择出发日期" />
        </a-form-item>

        <a-form-item field="end_date" label="结束日期" :rules="[{ required: true, message: '请选择日期' }]">
          <a-date-picker v-model="form.end_date" style="width: 100%" placeholder="选择结束日期" />
        </a-form-item>

        <a-form-item field="travelers" label="出行人数">
          <a-input-number v-model="form.travelers" :min="1" :max="20" style="width: 160px" />
        </a-form-item>

        <a-form-item field="budget" label="预算（元）">
          <a-input-number v-model="form.budget" :min="0" :step="500" style="width: 200px" />
        </a-form-item>

        <a-form-item>
          <a-space>
            <a-button type="primary" html-type="submit" :loading="submitting">
              <template #icon><icon-plus /></template>
              创建行程
            </a-button>
            <a-button @click="router.push('/my-trips')">返回我的行程</a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { tripApi } from '@/api/trips'

const router = useRouter()
const submitting = ref(false)

const form = reactive({
  destination: '',
  start_date: '',
  end_date: '',
  travelers: 2,
  budget: 0,
})

const handleSubmit = async ({ errors }: { errors?: Record<string, unknown> | undefined }) => {
  if (errors) return
  if (!form.start_date || !form.end_date) {
    Message.error('请选择出发与结束日期')
    return
  }
  submitting.value = true
  try {
    await tripApi.create({
      destination: form.destination.trim(),
      start_date: form.start_date,
      end_date: form.end_date,
      travelers: form.travelers || 1,
      budget: form.budget || 0,
    })
    Message.success('行程已创建')
    router.push('/my-trips')
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '创建失败，请重试')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.trip-create-page { max-width: 560px; margin: 0 auto; padding: 8px 16px 32px; }
.page-header h1 { font-size: 24px; margin: 0 0 20px; }
</style>