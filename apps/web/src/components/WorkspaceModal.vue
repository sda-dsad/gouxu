<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount} from 'vue'
defineProps<{title:string}>()
const emit=defineEmits<{close:[]}>(),dialog=ref<HTMLDialogElement>()
let previous:HTMLElement|null=null
onMounted(()=>{previous=document.activeElement as HTMLElement;dialog.value?.showModal()})
onBeforeUnmount(()=>{dialog.value?.close();if(previous?.isConnected)previous.focus()})
function backdrop(event:MouseEvent){if(event.target!==dialog.value)return;const box=dialog.value.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)emit('close')}
</script>
<template>
<Teleport to="body"><dialog ref="dialog" class="workspace-modal" aria-labelledby="workspace-modal-title" @cancel.prevent="emit('close')" @click="backdrop"><header><h2 id="workspace-modal-title">{{title}}</h2><button aria-label="关闭分析窗口" @click="emit('close')">关闭 ×</button></header><div class="workspace-modal-body"><slot/></div></dialog></Teleport>
</template>
