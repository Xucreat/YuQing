<template>
  <div class="sources-page" v-loading="loading">
    <div class="source-grid">
      <div v-for="s in sources" :key="s.name" class="card source-card">
        <div class="sc-header"><div class="sc-name">{{ s.name }}</div>
          <span class="pill" :class="statusPill(s.status)">{{ statusText(s.status) }}</span></div>
        <div class="sc-body">
          <div class="sc-stat"><div class="sc-label">舆情总数</div><div class="sc-value">{{ s.opinion_count?.toLocaleString() || "0" }}</div></div>
          <div class="sc-stat"><div class="sc-label">最后采集</div><div class="sc-value sc-time">{{ s.last_run ? new Date(s.last_run).toLocaleString("zh-CN") : "-" }}</div></div>
          <div class="sc-stat"><div class="sc-label">累计抓取</div><div class="sc-value">{{ s.total_collected?.toLocaleString() || "0" }}</div></div>
        </div></div></div>
    <div class="card table-card" style="margin-top:18px">
      <h3 style="padding:18px 18px 0;margin:0;font-size:16px">采集历史</h3>
      <table class="tbl"><thead><tr>
        <th style="width:170px">时间</th><th>采集器</th><th style="width:80px">抓取</th><th style="width:80px">新增</th><th style="width:80px">分析</th><th style="width:80px">状态</th>
      </tr></thead><tbody>
        <tr v-for="r in history" :key="r.id">
          <td>{{ formatTime(r.start_time) }}</td><td>{{ r.collector_name }}</td>
          <td>{{ r.fetched_raw }}</td><td>{{ r.created }}</td><td>{{ r.analyzed }}</td>
          <td><span class="pill" :class="statusPill(r.status)">{{ statusText(r.status) }}</span></td>
        </tr>
        <tr v-if="!history.length"><td colspan="6" class="empty-row">暂无采集记录</td></tr>
      </tbody></table></div>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from "vue";import { ElMessage } from "element-plus";import api from "@/api"
interface SourceItem{name:string;status:string;last_run:string|null;total_collected:number;total_created:number;opinion_count:number}
interface HistoryItem{id:number;collector_name:string;start_time:string|null;fetched_raw:number;created:number;analyzed:number;status:string}
const loading=ref(false);const sources=ref<SourceItem[]>([]);const history=ref<HistoryItem[]>([])
function statusPill(s:string):string{const m:Record<string,string>={running:"pill-green",completed:"pill-green",limited:"pill-orange",failed:"pill-red",error:"pill-red",unknown:"pill-gray"};return m[s]||"pill-gray"}
function statusText(s:string):string{const m:Record<string,string>={running:"正常",completed:"完成",limited:"受限",failed:"失败",error:"异常"};return m[s]||s||"未知"}
function formatTime(t:string|null):string{if(!t)return"-";return t.replace("T"," ").slice(0,19)}
async function loadData(){loading.value=true;try{const[sRes,hRes]=await Promise.all([api.get("/sources/status"),api.get("/sources/history",{params:{page:1,size:20}})]);sources.value=sRes.data.sources||[];history.value=hRes.data.items||[]}catch(err:any){ElMessage.error("加载失败")}finally{loading.value=false}}
onMounted(()=>loadData())
</script>
<style scoped>
.sources-page{min-height:100%}.source-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px}
.card{background:#fff;border-radius:18px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 12px 32px rgba(0,0,0,.05)}.source-card{padding:22px 24px}
.sc-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.sc-name{font-size:16px;font-weight:600;color:#1d1d1f}.sc-body{display:flex;gap:24px}
.sc-stat{flex:1}.sc-label{font-size:12px;color:#86868b;margin-bottom:4px}.sc-value{font-size:16px;font-weight:600;color:#1d1d1f}.sc-time{font-size:12px}
.table-card{padding:6px 6px 14px;overflow:hidden}
table.tbl{width:100%;border-collapse:collapse;font-size:14px}table.tbl thead th{text-align:left;font-size:12.5px;font-weight:600;color:#86868b;padding:14px 18px;border-bottom:1px solid #e8e8ed}
table.tbl tbody td{padding:15px 18px;border-bottom:1px solid #e8e8ed;color:#1d1d1f}table.tbl tbody tr:last-child td{border-bottom:none}
.empty-row td{text-align:center;color:#86868b;padding:40px 0}
.pill{display:inline-flex;align-items:center;gap:6px;padding:4px 11px;border-radius:980px;font-size:13px;font-weight:500}
.pill-green{background:rgba(52,199,89,.12);color:#1a8e3c}.pill-red{background:rgba(255,59,48,.1);color:#ff3b30}.pill-orange{background:rgba(255,159,10,.12);color:#c77700}.pill-gray{background:rgba(110,110,115,.12);color:#6e6e73}
</style>