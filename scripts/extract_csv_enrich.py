#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_csv_enrich.py — 从 Downloads 专业版 CSV 全量补列到 dashboard_data.json

覆盖板块:
  1. 换电柜(cabinet): last_upload_info_pro_*.csv → DATA.device.cabinet_detail (52列)
  2. 电池(battery):    last_upload_pro_*.csv       → DATA.device.battery_detail (33列)
  3. 网点(site):       site_info_pro_*.csv          → DATA.site.detail (60+列, 合并覆盖)
  4. 用户(user):       exchange_agreement_pro_*.csv  → DATA.user.detail (56列, 按 user_id 回挂)
  5. 优惠券-订单:      coupon_order_pro_*.csv        → DATA.coupon.agent_issue (50+列)
  6. 优惠券-发放:      agency_give_coupon_pro_*.csv  → DATA.coupon.merchant_issue (29列)

用法:
  python scripts/extract_csv_enrich.py

依赖: 无 DB 连接，纯本地 CSV 读取 + JSON 写入
"""

import csv
import json
import os
import sys
import shutil
import time
from datetime import datetime

# ── 路径 ──
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_PATH = os.path.join(ROOT, 'data', 'dashboard_data.json')
DOWNLOADS = os.path.join(os.path.expanduser('~'), 'Downloads')

# ── CSV 文件映射 (优先取最新的) ──
def find_latest(pattern):
    """在 Downloads 中找匹配 pattern 的最新文件"""
    files = []
    if os.path.isdir(DOWNLOADS):
        for f in os.listdir(DOWNLOADS):
            if pattern in f and f.endswith('.csv'):
                fp = os.path.join(DOWNLOADS, f)
                files.append((os.path.getmtime(fp), fp))
    if not files:
        return None
    files.sort(reverse=True)
    print(f"  [CSV] {pattern} → {os.path.basename(files[0][1])} ({datetime.fromtimestamp(files[0][0])})")
    return files[0][1]


# ════════════════════════════════════════════════
# 1. 换电柜 — last_upload_info_pro → cabinet_detail
# ════════════════════════════════════════════════
CAB_CSV_COLS = {
    '换电柜ID': 'cabinet_id',
    '设备ID': 'device_id',
    '设备SN': 'sn',
    '在线状态': 'is_online',
    '设备型号': 'cabinet_type',
    '协议版本': 'protocol_version',
    '网点ID': 'site_id',
    '网点名称': 'site_name',
    '网点状态': 'site_status',
    '网点开业时间': 'site_open_time',
    '网点首次绑定时间': 'site_first_bind',
    '网点最新绑定时间': 'site_last_bind',
    '网点联系人': 'site_contact',
    '联系人电话': 'site_contact_phone',
    '业务员名称': 'salesman',
    '网点受益人ID': 'beneficiary_id',
    '网点收益人姓名': 'beneficiary_name',
    '网点收益人手机号': 'beneficiary_phone',
    '省': 'province',
    '市': 'city',
    '区': 'district',
    '街道': 'street',
    '社区': 'community',
    '详细地址': 'address',
    '最后上线时间': 'last_online',
    '最后离线时间': 'last_offline',
    '最后上报时间': 'last_upload',
    '标签': 'tags',
    '主控软件版本': 'mcu_sw_version',
    '主控硬件版本': 'mcu_hw_version',
    '检测板软件版本': 'detector_sw_version',
    '检测板硬件版本': 'detector_hw_version',
    '总仓位数': 'slots',
    '有电池仓位数': 'slots_with_battery',
    '可换仓位数': 'slots_swap',
    '可还仓位数': 'slots_return',
    '空仓仓位数': 'slots_empty',
    '锁仓仓位数': 'slots_locked',
    '充电异常仓位数': 'slots_error',           # ← 映射到 error (前端用)
    '实时电压': 'voltage',
    '实时电流': 'current',
    '电表度数': 'meter_kwh',
    '备电状态': 'backup_status',
    '备电电压': 'backup_voltage',
    '后仓门状态': 'rear_door_status',
    '烟感检测': 'smoke_alarm',
    '水浸检测': 'water_alarm',
    '灭火器': 'fire_extinguisher',
    '近1个月换电次数': 'swap_count_30d',
    '近1个月换电用户数': 'swap_users_30d',
    '近3个月换电次数': 'swap_count_90d',
    '近3个月换电用户数': 'swap_users_90d',
    '近1个月换电失败订单数': 'swap_fail_30d',
}


def load_cabinet(csv_path):
    """加载换电柜 CSV → list of dict (英文 key)"""
    rows = []
    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        # 构建 mapping (中文→英文)
        col_map = {}
        for cn in fieldnames:
            en = CAB_CSV_COLS.get(cn)
            if en:
                col_map[cn] = en
            else:
                # 未映射的保留原列名(转小写下划线)
                col_map[cn] = cn.lower().replace(' ', '_')
        
        for raw in reader:
            row = {}
            for cn, en in col_map.items():
                v = raw.get(cn, '').strip()
                # 数字型字段尝试转换
                if en in ('cabinet_id','device_id','site_id','beneficiary_id',
                          'slots','slots_with_battery','slots_swap','slots_return',
                          'slots_empty','slots_locked','slots_error',
                          'voltage','current','meter_kwh','backup_voltage',
                          'swap_count_30d','swap_users_30d','swap_count_90d',
                          'swap_users_90d','swap_fail_30d'):
                    try:
                        row[en] = int(v) if v else 0
                    except ValueError:
                        try:
                            row[en] = float(v) if v else 0
                        except ValueError:
                            row[en] = v or 0
                else:
                    row[en] = v if v else ''
            rows.append(row)
    
    print(f"  换电柜: {len(rows)} 条, 字段 {len(col_map)} 个")
    return rows


# ════════════════════════════════════════════════
# 2. 电池 — last_upload_pro → battery_detail
# ════════════════════════════════════════════════
BAT_CSV_COLS = {
    '设备ID': 'device_id',
    '设备SN': 'sn',
    '标签': 'tags',
    '设备型号': 'model',
    '协议版本': 'protocol_version',
    '软件版本': 'sw_version',
    '硬件版本': 'hw_version',
    '仓位类型': 'slot_type',
    '仓位名称': 'slot_name',
    '最后流通时间': 'last_flow_time',
    '入库时间': 'inbound_time',
    '换电柜': 'cabinet_sn',
    '网点ID': 'site_id',
    '网点名称': 'site_name',
    '代理商': 'agency',
    '用户手机号': 'user_phone',
    '电池电量': 'soc',
    '在线状态': 'online',
    '最后上线时间': 'last_online',
    '最后离线时间': 'last_offline',
    '最后上报时间': 'last_report',
    '最后整机上报时间': 'last_full_report',
    '最后有效定位': 'last_gps',
    '查询定位地址': 'query_location',
    '最后有效定位地址': 'last_location',
    '最后有效定位类型': 'location_type',
    '最后有效定位精度(米)': 'location_accuracy',
    '最后有效定位时间': 'location_time',
    '充电状态': 'charge_status',
    '放电状态': 'discharge_status',
    '循环次数': 'cycle_count',
    '电压': 'voltage',
    '电流': 'current',
    'ACC（低功耗）': 'acc_low_power',
    'DET状态': 'det_status',
    '充电接口温度': 'charge_temp',
    '放电接口温度': 'discharge_temp',
    'BMS最大温度': 'bms_max_temp',
    'BMS最小温度': 'bms_min_temp',
    '电芯信息': 'cell_info',
    '借出次数(30天)': 'lending_30d',
    '借出次数(90天)': 'lending_90d',
}


def load_battery(csv_path):
    """加载电池 CSV → list of dict"""
    rows = []
    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        col_map = {}
        for cn in fieldnames:
            en = BAT_CSV_COLS.get(cn)
            if en:
                col_map[cn] = en
            else:
                col_map[cn] = cn.lower().replace(' ', '_').replace('（', '(').replace('）', ')')
        
        for raw in reader:
            row = {}
            for cn, en in col_map.items():
                v = raw.get(cn, '').strip()
                numeric_fields = ('device_id','site_id','soc','cycle_count','voltage','current',
                                  'charge_temp','discharge_temp','bms_max_temp','bms_min_temp',
                                  'location_accuracy','lending_30d','lending_90d')
                if en in numeric_fields:
                    try:
                        row[en] = int(v) if v else 0
                    except ValueError:
                        try:
                            row[en] = float(v) if v else 0.0
                        except ValueError:
                            row[en] = v or 0
                else:
                    row[en] = v if v else ''
            rows.append(row)
    
    print(f"  电池: {len(rows)} 条, 字段 {len(col_map)} 个")
    return rows


# ════════════════════════════════════════════════
# 3. 网点 — site_info_pro → site detail (合并/覆盖)
# ════════════════════════════════════════════════
SITE_CSV_COLS = {
    '网点id': 'id',
    '网点名称': 'name',
    '网点标签': 'tags',
    '商户ID': 'merchant_id',
    '商户名称': 'merchant_name',
    '网点行业': 'industry',
    '收益人id': 'beneficiary_id',
    '收益人姓名': 'beneficiary_name',
    '收益人手机号': 'beneficiary_phone',
    '独立电表状态': 'meter_status',
    '电费结算方式': 'fee_settle_method',
    '电费结算周期': 'fee_settle_cycle',
    '最近结算时间': 'last_settle_time',
    '联系人姓名': 'contact_person_name',
    '联系人手机号': 'tel',
    '业务员id': 'salesman_id',
    '业务员名称': 'salesman',
    '审核状态': 'audit_status',
    '换电柜状态': 'cabinet_status',
    '换电柜数量': 'cabinet_count',
    '换电柜离线数量': 'cabinet_offline_count',
    '柜内电池数量': 'battery_in_cabinet',
    '创建时间': 'create_time',
    '开业时间': 'open_time',
    '代理商id': 'agency_id',
    '代理商名称': 'agency_name',
    '渠道商id': 'channel_id',
    '渠道商名称': 'channel_name',
    '城市': 'city',
    '区域': 'area',
    '街道': 'street',
    '社区': 'community',
    '详细地址': 'address',
    '电池产品id': 'battery_product_id',
    '电池产品名称': 'battery_product',
    '换电收费标准': 'swap_fee_standard',
    '是否换电': 'is_swap',
    '是否售车': 'is_sell_vehicle',
    '换电柜sn': 'cabinet_sn_list',
    '收入项': 'income_items',
    '室内/室外': 'indoor_outdoor',
    '是否24小时': 'is_24h',
    '开业申请时间': 'open_apply_time',
    '开业申请人': 'open_applicant',
    '开业审批时间': 'open_approve_time',
    '开业审批人': 'open_approver',
    '开业送货完成时间': 'open_delivery_time',
    '开业送货人': 'open_delivery_person',
    '开业安装时间': 'open_install_time',
    '开业安装人': 'open_install_person',
    '开业验收时间': 'open_accept_time',
    '开业验收人': 'open_accept_person',
    '确认开业人': 'confirm_open_person',
    '累计签约用户数': 'total_sign_users',
    '累计退订用户数': 'total_unsub_users',
    '近1个月签约用户数': 'sign_users_30d',
    '近1个月退订用户数': 'unsub_users_30d',
    '近3个月签约用户数': 'sign_users_90d',
    '近3个月退订用户数': 'unsub_users_90d',
    '近3天换电次数': 'swap_3d',
    '近7天换电次数': 'swap_7d',
    '近1个月换电次数': 'swap_30d',
    '近3个月换电次数': 'swap_90d',
    '总换电数': 'total_swap_count',
    '最后一次换电实际': 'last_swap_time',
}


def load_site(csv_path):
    """加载网点 CSV → list of dict, 以 id 为 key 建 lookup"""
    rows = []
    id_map = {}  # id → row index
    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        col_map = {}
        for cn in fieldnames:
            en = SITE_CSV_COLS.get(cn)
            if en:
                col_map[cn] = en
            else:
                col_map[cn] = cn.lower().replace(' ', '_').replace('/', '_')
        
        for raw in reader:
            row = {}
            for cn, en in col_map.items():
                v = raw.get(cn, '').strip()
                # 清理可能的换行符
                v = v.replace('\n', '').replace('\r', '').replace('\t', '')
                numeric_fields = ('id','merchant_id','beneficiary_id','salesman_id',
                                  'cabinet_count','cabinet_offline_count','battery_in_cabinet',
                                  'agency_id','channel_id','battery_product_id',
                                  'total_sign_users','total_unsub_users',
                                  'sign_users_30d','unsub_users_30d','sign_users_90d','unsub_users_90d',
                                  'swap_3d','swap_7d','swap_30d','swap_90d','total_swap_count')
                if en in numeric_fields:
                    try:
                        row[en] = int(v) if v else 0
                    except ValueError:
                        row[en] = v or 0
                else:
                    row[en] = v if v else ''
            
            # 用 id 去重
            rid = str(row.get('id', ''))
            if rid and rid not in id_map:
                id_map[rid] = len(rows)
                rows.append(row)
            elif rid in id_map:
                # 合并：新值覆盖空值
                existing = rows[id_map[rid]]
                for k, val in row.items():
                    if val and not existing.get(k):
                        existing[k] = val
    
    print(f"  网点: {len(rows)} 条 (去重后), 字段 {len(col_map)} 个")
    return rows


# ════════════════════════════════════════════════
# 4. 用户 — exchange_agreement_pro → user detail (按 user_id 回挂)
# ════════════════════════════════════════════════
AGR_CSV_COLS = {
    '换电服务协议ID': 'agreement_id',
    '协议类型': 'agreement_type',
    '用户ID': 'user_id',
    '用户手机号': 'phone',
    '企业ID': 'enterprise_id',
    '企业名称': 'enterprise_name',
    '企业管理员手机号': 'enterprise_admin_phone',
    '电池产品': 'battery_product',
    '签约网点ID': 'site_id',
    '签约网点名称': 'site_name',
    '协议状态': 'status',
    '协议激活时间': 'activate_time',
    '协议终止时间': 'terminate_time',
    '电池系列ID': 'battery_series_id',
    '使用时长': 'usage_duration',
    '租期剩余时长': 'rent_remaining',
    '协议到期时间': 'expire_time',
    '签约代理商ID': 'agency_id',
    '网点渠道商ID': 'channel_id',
    '城市': 'city',
    '地区': 'area',
    '街道': 'street',
    '网点导购ID': 'guide_id',
    '网点导购名称': 'guide_name',
    '网点导购手机号': 'guide_phone',
    '导购是否店长': 'guide_is_manager',
    '签约网点业务员ID': 'site_salesman_id',
    '签约网点业务员名称': 'site_salesman_name',
    '网点当前业务员ID': 'current_salesman_id',
    '网点当前业务员名称': 'current_salesman_name',
    '首次签约套餐ID': 'first_package_id',
    '首次签约套餐名称': 'first_package_name',
    '首次签约套餐原价': 'first_package_original_price',
    '首次签约套餐实付价格': 'first_package_price',
    '最后购买套餐ID': 'last_package_id',
    '最后购买套餐名称': 'last_package_name',
    '最后购买套餐原价': 'last_package_original_price',
    '最后购买套餐实付价格': 'last_package_price',
    '车辆数量': 'vehicle_count',
    '当前使用套餐ID': 'current_package_id',
    '当前使用套餐名称': 'current_package_name',
    '当前使用套餐原价': 'current_package_original_price',
    '当前使用套餐实付价格': 'current_package_price',
    '当前套餐到期时间': 'current_package_expire',
    '累计续租次数': 'renewal_count',
    '累计续租金额': 'renewal_amount',
    '累计服务单支付金额': 'total_paid_amount',
    '累计服务单退款金额': 'total_refund_amount',
    '累计服务单优惠券支付金额': 'coupon_paid_amount',
    '销售场景id': 'scene_id',
    '推广员id': 'promoter_id',
    '推广员名称': 'promoter_name',
    '销售场景名称': 'scene_name',
    '是否合约车': 'is_contract_vehicle',
    '合约方案ID': 'contract_scheme_id',
    '合约方案名称': 'contract_scheme_name',
    '押金状态': 'deposit_status',
    '押金方式': 'deposit_method',
    '押金金额': 'deposit_amount',
    '违约次数': 'violation_count',
    '违约合计时长': 'violation_total_duration',
    '违约支付金额': 'violation_amount',
}


def load_agreement(csv_path):
    """加载协议 CSV → list of dict, 以 user_id 为 key 建 lookup"""
    rows = []
    uid_map = {}
    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        col_map = {}
        for cn in fieldnames:
            en = AGR_CSV_COLS.get(cn)
            if en:
                col_map[cn] = en
            else:
                col_map[cn] = cn.lower().replace(' ', '_').replace('（', '(').replace('）', ')')
        
        for raw in reader:
            row = {}
            for cn, en in col_map.items():
                v = raw.get(cn, '').strip()
                v = v.replace('\n', '').replace('\r', '').replace('\t', '')
                numeric_fields = ('agreement_id','user_id','enterprise_id','site_id','agency_id','channel_id',
                                  'guide_id','site_salesman_id','current_salesman_id',
                                  'first_package_id','last_package_id','current_package_id',
                                  'vehicle_count','renewal_count','renewal_amount',
                                  'total_paid_amount','total_refund_amount','coupon_paid_amount',
                                  'scene_id','promoter_id','contract_scheme_id',
                                  'deposit_amount','violation_count','violation_total_duration','violation_amount')
                if en in numeric_fields:
                    try:
                        row[en] = int(v) if v else 0
                    except ValueError:
                        try:
                            row[en] = float(v) if v else 0.0
                        except ValueError:
                            row[en] = v or 0
                else:
                    row[en] = v if v else ''
            
            uid = str(row.get('user_id', ''))
            if uid and uid not in uid_map:
                uid_map[uid] = len(rows)
                rows.append(row)
            elif uid in uid_map:
                existing = rows[uid_map[uid]]
                for k, val in row.items():
                    if val and not existing.get(k):
                        existing[k] = val
    
    print(f"  协议(用户): {len(rows)} 条 (去重后), 字段 {len(col_map)} 个")
    return rows, uid_map


# ════════════════════════════════════════════════
# 5. 优惠券-订单 — coupon_order_pro → coupon.agent_issue
# ════════════════════════════════════════════════
COUPON_ORDER_COLS = {
    '兑换码ID': 'code_id',
    '订单ID': 'order_id',
    '代理商ID': 'agency_id',
    '代理商名称': 'agency_name',
    '商户ID': 'merchant_id',
    '商户名称': 'merchant_name',
    '优惠券资源ID': 'coupon_resource_id',
    '优惠券资源名称': 'coupon_resource_name',
    '兑换码批次ID': 'batch_id',
    '是否已兑换': 'is_redeemed',
    '兑换时间': 'redeem_time',
    '发放人ID': 'issuer_id',
    '发放人名称': 'issuer_name',
    '发放人类型': 'issuer_type',
    '兑换用户ID': 'redeem_user_id',
    '兑换用户名称': 'redeem_user_name',
    '兑换用户手机号': 'redeem_user_phone',
    '是否已使用': 'is_used',
    '使用时间': 'use_time',
    '是否已作废': 'is_voided',
    '作废时间': 'void_time',
    '协议ID': 'agreement_id',
    '签约网点ID': 'site_id',
    '签约网点名称': 'site_name',
    '服务单ID': 'service_id',
    '是否已退款': 'is_refund',
    '退款金额（元）': 'refund_amount',
    '退款原因': 'refund_reason',
    '退款时间': 'refund_time',
    '退款操作人ID': 'refund_operator_id',
    '退款操作人名称': 'refund_operator_name',
    '订单购买券码数量（不包含已作废的）': 'order_code_count',
    '订单可发放券码数量': 'order_available_count',
    '订单已发放券码数量': 'order_issued_count',
    '订单已核销券码数量': 'order_used_count',
    '领券中心ID': 'center_id',
    '领取记录ID': 'record_id',
    '电池产品ID': 'battery_product_id',
    '电池产品名称': 'battery_product_name',
    '支付渠道': 'pay_channel',
    '支付渠道流水': 'pay_channel_no',
    '支付单号': 'pay_no',
    '订单状态': 'order_status',
    '立马支付': 'immediate_pay',
    '是否已支付': 'is_paid',
    '支付时间': 'pay_time',
    '订单总支付金额（元）': 'order_total_amount',
    '券码支付单价（元）': 'code_unit_price',
    '购买人ID': 'buyer_id',
    '购买人名称': 'buyer_name',
    '购买人类型': 'buyer_type',
    '下单人ID': 'orderer_id',
    '下单人名称': 'orderer_name',
    '下单人类型': 'orderer_type',
    '创建时间': 'create_time',
}


def load_coupon_order(csv_path):
    """加载优惠券订单 CSV → list of dict"""
    rows = []
    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        col_map = {}
        for cn in fieldnames:
            en = COUPON_ORDER_COLS.get(cn)
            if en:
                col_map[cn] = en
            else:
                col_map[cn] = cn.lower().replace(' ', '_').replace('（', '(').replace('）', ')').replace('（', '(').replace('）', ')')
        
        for raw in reader:
            row = {}
            for cn, en in col_map.items():
                v = raw.get(cn, '').strip()
                numeric_fields = ('code_id','order_id','agency_id','merchant_id','coupon_resource_id','batch_id',
                                  'issuer_id','redeem_user_id','agreement_id','site_id','service_id',
                                  'refund_amount','order_code_count','order_available_count','order_issued_count','order_used_count',
                                  'center_id','record_id','battery_product_id','order_total_amount','code_unit_price',
                                  'buyer_id','orderer_id')
                if en in numeric_fields:
                    try:
                        row[en] = int(v) if v else 0
                    except ValueError:
                        try:
                            row[en] = float(v) if v else 0.0
                        except ValueError:
                            row[en] = v or 0
                else:
                    row[en] = v if v else ''
            rows.append(row)
    
    print(f"  优惠券-订单: {len(rows)} 条, 字段 {len(col_map)} 个")
    return rows


# ════════════════════════════════════════════════
# 6. 优惠券-发放 — agency_give_coupon_pro → coupon.merchant_issue
# ════════════════════════════════════════════════
COUPON_GIVE_COLS = {
    '发放记录ID': 'record_id',
    '优惠券名称': 'coupon_name',
    '优惠券兑换码': 'coupon_code',
    '发放人ID': 'issuer_id',
    '发放人名称': 'issuer_name',
    '发放人手机号': 'issuer_phone',
    '发放时间': 'issue_time',
    '是否需业务员购买': 'need_purchase',
    '领取用户ID': 'receiver_id',
    '领取用户名称': 'receiver_name',
    '领取用户手机号': 'receiver_phone',
    '优惠券使用状态': 'usage_status',
    '换电协议ID': 'agreement_id',
    '换电协议状态': 'agreement_status',
    '电池产品ID': 'battery_product_id',
    '电池产品名称': 'battery_product_name',
    '签约网点ID': 'site_id',
    '签约网点名称': 'site_name',
    '签约套餐ID': 'package_id',
    '签约套餐名称': 'package_name',
    '车辆品牌ID': 'brand_id',
    '车辆品牌名称': 'brand_name',
    '应付金额（元）': 'due_amount',
    '支付状态': 'pay_status',
    '实付金额（元）': 'paid_amount',
    '支付时间': 'pay_time',
    '支付方式': 'pay_method',
    '支付流水号': 'pay_no',
    '无需支付备注': 'no_pay_note',
    '退款状态': 'refund_status',
    '退款金额（元）': 'refund_amount',
    '退款时间': 'refund_time',
}


def load_coupon_give(csv_path):
    """加载优惠券发放 CSV → list of dict"""
    rows = []
    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        col_map = {}
        for cn in fieldnames:
            en = COUPON_GIVE_COLS.get(cn)
            if en:
                col_map[cn] = en
            else:
                col_map[cn] = cn.lower().replace(' ', '_').replace('（', '(').replace('）', ')')
        
        for raw in reader:
            row = {}
            for cn, en in col_map.items():
                v = raw.get(cn, '').strip()
                numeric_fields = ('record_id','issuer_id','receiver_id','agreement_id','battery_product_id',
                                  'site_id','package_id','brand_id','due_amount','paid_amount','refund_amount')
                if en in numeric_fields:
                    try:
                        row[en] = int(v) if v else 0
                    except ValueError:
                        try:
                            row[en] = float(v) if v else 0.0
                        except ValueError:
                            row[en] = v or 0
                else:
                    row[en] = v if v else ''
            rows.append(row)
    
    print(f"  优惠券-发放: {len(rows)} 条, 字段 {len(col_map)} 个")
    return rows


# ════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════
def main():
    t0 = time.time()
    print("=" * 60)
    print("CSV ENRICH — 从专业版 CSV 补全各模块明细数据")
    print("=" * 60)
    
    # ── 0. 备份 ──
    if os.path.exists(DATA_PATH):
        bak = DATA_PATH + '.bak_pre_csv'
        shutil.copy2(DATA_PATH, bak)
        print(f"\n[备份] {os.path.getsize(bak)//1024//1024}MB → {os.path.basename(bak)}")
    
    # ── 1. 加载 JSON ──
    print("\n[1/5] 加载 dashboard_data.json ...")
    with open(DATA_PATH, encoding='utf-8') as f:
        D = json.load(f)
    print(f"  JSON 大小: {os.path.getsize(DATA_PATH)//1024//1024}MB")
    
    # 确保 device 节点存在
    if 'device' not in D:
        D['device'] = {}
    
    # ── 2. 换电柜 ──
    print("\n[2/6] 换电柜明细 ...")
    cab_csv = find_latest('last_upload_info_pro')
    if cab_csv:
        cab_rows = load_cabinet(cab_csv)
        D['device']['cabinet_detail'] = cab_rows
        D['device']['cabinet_total'] = len(cab_rows)
        # 统计 KPI
        online = sum(1 for r in cab_rows if r.get('is_online') == '在线')
        offline = sum(1 for r in cab_rows if r.get('is_online') == '离线')
        fault = sum(1 for r in cab_rows if int(r.get('slots_error', 0)) > 0)
        D['device']['cabinet_kpis'] = {
            'total': len(cab_rows),
            'online': online,
            'offline': offline,
            'fault': fault,
        }
        print(f"  KPI: 总{len(cab_rows)} / 在线{online} / 离线{offline} / 故障{fault}")
    else:
        print("  ⚠️ 未找到 last_upload_info_pro CSV，跳过换电柜")
    
    # ── 3. 电池 ──
    print("\n[3/6] 电池明细 ...")
    bat_csv = find_latest('last_upload_pro')
    # 排除 info 版（那是换电柜），取纯 last_upload_pro
    if bat_csv and 'info' not in os.path.basename(bat_csv).lower():
        bat_rows = load_battery(bat_csv)
        D['device']['battery_detail'] = bat_rows
        D['device']['battery_total'] = len(bat_rows)
        online_bat = sum(1 for r in bat_rows if r.get('online') == '在线' or r.get('is_online') == '在线')
        print(f"  KPI: 总{len(bat_rows)} / 在线约{online_bat}")
    else:
        # 尝试找非 info 版
        if os.path.isdir(DOWNLOADS):
            candidates = [f for f in os.listdir(DOWNLOADS) 
                         if f.startswith('last_upload_pro_') and f.endswith('.csv') and 'info' not in f.lower()]
            if candidates:
                candidates.sort(key=lambda x: os.path.getmtime(os.path.join(DOWNLOADS, x)), reverse=True)
                bat_path = os.path.join(DOWNLOADS, candidates[0])
                print(f"  使用: {candidates[0]}")
                bat_rows = load_battery(bat_path)
                D['device']['battery_detail'] = bat_rows
                D['device']['battery_total'] = len(bat_rows)
            else:
                print("  ⚠️ 未找到 last_upload_pro CSV (非 info 版)，跳过电池")
        else:
            print("  ⚠️ Downloads 目录不存在，跳过电池")
    
    # ── 4. 网点 ──
    print("\n[4/6] 网点明细 ...")
    site_csv = find_latest('site_info_pro')
    if site_csv:
        site_rows = load_site(site_csv)
        # 完全替换 site.detail（CSV 是全量导出）
        D['site']['detail'] = site_rows
        D['site']['site_detail'] = site_rows
        D['site']['site_total'] = len(site_rows)
        print(f"  已替换 site.detail ({len(site_rows)} 条)")
    else:
        print("  ⚠️ 未找到 site_info_pro CSV，跳过网点")
    
    # ── 5. 用户/协议 ──
    print("\n[5/6] 用户协议明细 ...")
    agr_csv = find_latest('exchange_agreement_pro')
    if agr_csv:
        agr_rows, uid_map = load_agreement(agr_csv)
        # 回挂到现有 user.detail (按 user_id 匹配补充)
        existing_ud = D.get('user', {}).get('detail', [])
        if existing_ud:
            merged = 0
            for eu in existing_ud:
                uid = str(eu.get('user_id', ''))
                if uid in uid_map:
                    src = agr_rows[uid_map[uid]]
                    for k, v in src.items():
                        if v and k not in eu:  # 不覆盖已有值
                            eu[k] = v
                    merged += 1
            print(f"  回挂合并: {merged}/{len(existing_ud)} 条 user.detail 匹配成功")
            
            # 对未匹配到的现有行也尝试用 phone 匹配
            phone_map = {}
            for ar in agr_rows:
                ph = str(ar.get('phone', '')).strip()
                if ph:
                    phone_map[ph] = ar
            extra_merge = 0
            for eu in existing_ud:
                if not eu.get('enterprise_name'):  # 还没被合并过的
                    ph = str(eu.get('phone', '')).strip()
                    if ph in phone_map:
                        src = phone_map[ph]
                        for k, v in src.items():
                            if v and k not in eu:
                                eu[k] = v
                        extra_merge += 1
            if extra_merge:
                print(f"  手机号二次匹配: 额外 {extra_merge} 条")
        else:
            # 没有 user.detail，直接用协议数据作为用户数据
            D.setdefault('user', {})['detail'] = agr_rows
            print(f"  直接写入 user.detail ({len(agr_rows)} 条)")
    else:
        print("  ⚠️ 未找到 exchange_agreement_pro CSV，跳过用户")
    
    # ── 6. 优惠券 ──
    print("\n[6/6] 优惠券明细 ...")
    D.setdefault('coupon', {})
    
    co_csv = find_latest('coupon_order_pro')
    if co_csv:
        co_rows = load_coupon_order(co_csv)
        D['coupon']['agent_issue'] = co_rows
        D['coupon']['agent_issue_total'] = len(co_rows)
    
    cg_csv = find_latest('agency_give_coupon_pro')
    if cg_csv:
        cg_rows = load_coupon_give(cg_csv)
        D['coupon']['merchant_issue'] = cg_rows
        D['coupon']['merchant_issue_total'] = len(cg_rows)
    
    if not co_csv and not cg_csv:
        print("  ⚠️ 未找到优惠券 CSV")
    
    # ── 写回 ──
    print(f"\n[写入] dashboard_data.json ...")
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(D, f, ensure_ascii=False, separators=(',', ':'))
    
    size = os.path.getsize(DATA_PATH) // 1024 // 1024
    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"✅ 完成! JSON={size}MB, 耗时 {elapsed:.1f}s")
    print(f"  device.cabinet_detail: {len(D.get('device',{}).get('cabinet_detail',[]))} 条")
    print(f"  device.battery_detail:  {len(D.get('device',{}).get('battery_detail',[]))} 条")
    print(f"  site.detail:            {len(D.get('site',{}).get('detail',[]))} 条")
    print(f"  user.detail:            {len(D.get('user',{}).get('detail',[]))} 条")
    print(f"  coupon.agent_issue:     {len(D.get('coupon',{}).get('agent_issue',[]))} 条")
    print(f"  coupon.merchant_issue:  {len(D.get('coupon',{}).get('merchant_issue',[]))} 条")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
