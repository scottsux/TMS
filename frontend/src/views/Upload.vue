<template>
  <div class="container" style="container-type:inline-size;">
    <PageHeader title="上传包裹" subtitle="保持录入区轻一点，只强调输入本身，不再用大外框包整块表单。" />

    <section class="mb-4 max-w-3xl mx-auto">
      <div class="upload-form">
        <template v-if="role!=='customer'">
          <div class="field-row">
            <label class="field-label">客户 ID</label>
            <input v-model.number="customer_id" class="input" placeholder="示例 1" type="number" min="1" aria-label="customer_id"/>
          </div>
        </template>
        <template v-else>
          <div class="field-row customer-pill">
            <label class="field-label">客户 ID</label>
            <div style="display:flex; align-items:center; gap:8px;">
            <span class="opacity-70">客户 ID</span>
            <span class="badge badge-info">{{ effectiveCustomerId }}</span>
            </div>
          </div>
        </template>
        <div class="field-row">
          <label class="field-label">运单号</label>
          <input v-model.trim="tracking_number" class="input" placeholder="唯一运单号" aria-label="tracking_number"/>
        </div>
        <div class="field-row field-grid">
          <div>
            <label class="field-label">快递公司</label>
            <input v-model.trim="courier_company" class="input" placeholder="如 SF" aria-label="courier_company"/>
          </div>
          <div>
            <label class="field-label">品类</label>
            <input v-model.trim="item_category" class="input" placeholder="如 化妆品" aria-label="item_category"/>
          </div>
        </div>
        <div class="field-row">
          <label class="field-label">物品描述</label>
          <input v-model.trim="item_description" class="input" placeholder="填写物品描述" aria-label="item_description"/>
        </div>
        <div class="field-row">
          <label class="field-label">备注</label>
          <input v-model.trim="note" class="input" placeholder="可选备注" aria-label="note"/>
        </div>
      </div>

      <div class="upload-meta">
        <div style="display:flex; align-items:center; gap:10px;">
          <label for="filePick" class="btn btn-primary" style="cursor:pointer;">选择图片</label>
          <span class="text-xs opacity-70">已选择 {{ files.length }} 张（可选，最多 5 张）</span>
        </div>
        <input id="filePick" type="file" accept="image/png,image/jpeg,image/webp" multiple @change="onFiles" style="position:absolute; width:1px; height:1px; opacity:0;"/>
        <ul v-if="fileErrors.length" class="text-xs" style="color:#b45309; margin-top:6px;">
          <li v-for="(e,i) in fileErrors" :key="i">• {{ e }}</li>
        </ul>
      </div>

      <div class="text-xs opacity-70" style="margin-top:5px;">提示：运单号需唯一，图片可选。</div>
      <div class="mt-8 mb-8 flex items-center gap-2" style="margin-top:10px;">
        <button class="btn btn-primary" @click="submit" :disabled="submitting">提交</button>
        <button class="btn btn-ghost" @click="resetForm" :disabled="submitting">清空</button>
        <span v-if="msg" class="text-xs" :style="{color: msgType==='ok' ? '#065f46' : '#b91c1c'}">{{ msg }}</span>
      </div>
    </section>

    <section class="max-w-3xl mx-auto" style="margin-top:10px;">
      <h2 class="text-base mb-2">预览</h2>
      <div class="overflow-x-auto preview-block">
        <table class="table table--compact table--zebra">
          <thead>
            <tr>
              <th>文件名</th>
              <th>大小</th>
              <th>格式</th>
              <th>状态</th>
              <th class="text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(f, i) in files" :key="i">
              <td>{{ f.name }}</td>
              <td>{{ pretty(f.size) }}</td>
              <td>{{ f.type.split('/')[1] || '-' }}</td>
              <td class="opacity-80">就绪</td>
              <td class="text-right">
                <button class="px-3 py-1.5 rounded-lg border text-xs" disabled>移除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '../stores/auth'
import api from '../api/client'
import PageHeader from '../components/PageHeader.vue'

const auth = useAuthStore()
const { role, user } = storeToRefs(auth)
// 对于 customer 角色，强制使用自己的 ID；staff 可填写任意客户 ID
const customer_id = ref(1)
const effectiveCustomerId = computed(() => role.value === 'customer' ? (user.value?.id ?? 1) : (Number(customer_id.value) || 1))
const tracking_number = ref('')
const courier_company = ref('')
const item_category = ref('')
const item_description = ref('')
const note = ref('')

const files = ref([])
const fileErrors = ref([])
const submitting = ref(false)
const msg = ref('')
const msgType = ref('ok')

function onFiles(e) {
  fileErrors.value = []
  const list = Array.from(e.target.files || [])
  if (list.length > 5) fileErrors.value.push('最多 5 张图片')
  const okTypes = new Set(['image/png','image/jpeg','image/webp'])
  let total = []
  for (const f of list) {
    if (!okTypes.has(f.type)) fileErrors.value.push(`${f.name} 格式不支持`)
    if (f.size > 5 * 1024 * 1024) fileErrors.value.push(`${f.name} 超过 5MB`)
    total.push(f)
  }
  files.value = total.slice(0,5)
}

function pretty(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB'
  return (bytes/1024/1024).toFixed(2) + ' MB'
}

async function submit() {
  msg.value = ''
  if (!tracking_number.value.trim()) {
    msg.value = 'tracking_number 必填（需唯一）'; msgType.value = 'err'; return
  }
  if (fileErrors.value.length) { msg.value = '请先修正图片校验问题'; msgType.value = 'err'; return }
  submitting.value = true
  try {
    const body = {
      customer_id: effectiveCustomerId.value,
      tracking_number: tracking_number.value.trim(),
      courier_company: courier_company.value.trim() || undefined,
      item_category: item_category.value.trim() || undefined,
      item_description: item_description.value.trim() || undefined,
      note: note.value.trim() || undefined,
    }
    const res = await api.post('/parcels', body)
    // upload files if any
    if (files.value && files.value.length) {
      const fd = new FormData()
      for (const f of files.value) fd.append('files', f, f.name)
      await api.upload(`/parcels/${res.id}/files`, fd)
      msg.value = `已创建包裹 #${res.id} 并上传 ${files.value.length} 张图片`
    } else {
      msg.value = `已创建包裹 #${res.id}（状态：${res.status}）`
    }
    msgType.value = 'ok'
    tracking_number.value = ''
    item_description.value = ''
    note.value = ''
    files.value = []
  } catch (e) {
    msg.value = '提交失败：' + (e?.message || '未知错误')
    msgType.value = 'err'
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  if (role.value !== 'customer') customer_id.value = 1
  tracking_number.value = ''
  courier_company.value = ''
  item_category.value = ''
  item_description.value = ''
  note.value = ''
  files.value = []
  fileErrors.value = []
  msg.value = ''
}
</script>

<style scoped>
.upload-form {
  display: grid;
  gap: 12px;
}

.field-row {
  display: grid;
  gap: 6px;
}

.field-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.customer-pill {
  padding-bottom: 4px;
}

.upload-meta {
  margin-top: 18px;
  margin-bottom: 8px;
}

.preview-block {
  border-top: 1px solid var(--border-soft);
  padding-top: 10px;
}

@media (max-width: 768px) {
  .field-grid {
    grid-template-columns: 1fr;
  }
}
</style>
