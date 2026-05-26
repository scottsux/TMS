export const ParcelStatus = {
  SUBMITTED: 'SUBMITTED',
  IN_TRANSIT: 'IN_TRANSIT',
  PACK_REQUESTED: 'PACK_REQUESTED',
  ARRIVED: 'ARRIVED',
  PACKED: 'PACKED',
  REJECTED: 'REJECTED',
}

export const OrderStatus = {
  DRAFT: 'DRAFT',
  READY_TO_PACK: 'READY_TO_PACK',
  PACKING: 'PACKING',
  COMPLETED: 'COMPLETED',
}

export const TaskStatus = {
  TODO: 'TODO',
  IN_PROGRESS: 'IN_PROGRESS',
  DONE: 'DONE',
}

export const zh = {
  parcel: {
    SUBMITTED: '提交', IN_TRANSIT: '在途', ARRIVED: '已到仓', PACK_REQUESTED: '申请打包', PACKED: '已打包', REJECTED: '已拒绝'
  },
  order: {
    DRAFT: '草稿', READY_TO_PACK: '待打包', PACKING: '打包中', COMPLETED: '已完成'
  },
  task: { TODO: '待办', IN_PROGRESS: '进行中', DONE: '已完成' }
}
