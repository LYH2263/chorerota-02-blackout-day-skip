<template>
  <div>
    <h1 class="brand">成员</h1>
    <form @submit.prevent="add">
      <input v-model="name" placeholder="新成员姓名" />
      <button type="submit">添加</button>
    </form>
    <p v-if="err" class="err">{{ err }}</p>
    <ul class="list">
      <li v-for="m in rows" :key="m.id">
        <strong>{{ m.name }}</strong>
        <span class="muted"> · {{ m.active ? '在岗' : '停用' }} · {{ m.data_quality }}</span>
        <div style="margin-top:4px">
          <span class="muted">忌日:</span>
          <label v-for="d in 7" :key="d" style="margin-right:6px">
            <input type="checkbox" :checked="(edit[m.id] || []).includes(d - 1)" @change="toggle(m.id, d - 1)" />
            D{{ d - 1 }}
          </label>
          <button @click="save(m.id)">保存忌日</button>
        </div>
      </li>
    </ul>
    <div class="week-card" style="margin-top:12px">
      <header>本周忌日快照（生成时钉住，改现行忌日不回刷）</header>
      <p v-if="!snapshot.length" class="muted">本周尚未生成或无忌日</p>
      <p v-for="t in snapshot" :key="t.member_id">{{ t.name }} 忌: {{ t.days.map(d => 'D' + d).join('、') }}</p>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const rows = ref([])
const name = ref('')
const err = ref('')
const edit = ref({})
const snapshot = ref([])
const weekId = 1
async function load() {
  rows.value = await api('/members')
  const e = {}
  for (const m of rows.value) e[m.id] = [...(m.taboo_days || [])]
  edit.value = e
  try {
    const b = await api('/weeks/' + weekId + '/board')
    snapshot.value = b.taboos || []
  } catch { snapshot.value = [] }
}
function toggle(mid, d) {
  const cur = edit.value[mid] || []
  edit.value[mid] = cur.includes(d) ? cur.filter(x => x !== d) : [...cur, d].sort((a, b) => a - b)
}
async function save(mid) {
  err.value = ''
  try {
    await api('/members/' + mid + '/taboos', { method: 'PUT', body: JSON.stringify({ days: edit.value[mid] || [] }) })
    await load()
  } catch (e) { err.value = e.message }
}
async function add() {
  if (!name.value.trim()) return
  await api('/members', { method: 'POST', body: JSON.stringify({ name: name.value }) })
  name.value = ''; await load()
}
onMounted(load)
</script>
