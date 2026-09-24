# -*- coding: utf-8 -*-
"""
网点明细全量补抽 · site_info_pro CSV → DATA.site.detail
=========================================================
将本地全量导出 site_info_pro_*.csv（10681 行 / 65 列）映射为
前端契约字段（与现有 site.detail[0] 的 64 个 key 完全一致），
替换当前仅 644 行的样本，使 网点列表 / 单网点视图 / 总览 覆盖全量网点。

字段映射：CSV 65 列 与 JSON 64 key 按位置对齐（已逐列核对）。
数值字段（柜数/用户数/换电次数）转 int，其余保留字符串。
不臆测 type/status（CSV 无独立列），沿用现有结构（缺省值由前端容错）。

产物：data/dashboard_data.json 的 site.detail / site.site_detail / site.site_total 刷新。
"""
import csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "dashboard_data.json")

# 全量导出 CSV（最新最大的一份）
CSVP = "C:/Users/Karry/Downloads/site_info_pro_20260630232957.csv"

# 前端契约字段（与现有 site.detail[0].keys() 顺序一致，共 64 个）
KEYS = ['id','name','tags','merchant_id','merchant_name','industry','beneficiary_id',
        'beneficiary_name','beneficiary_phone','meter_status','fee_settle_method','fee_settle_cycle',
        'last_settle_time','contact_person_name','tel','salesman_id','salesman','audit_status',
        'cabinet_status','cabinet_count','cabinet_offline_count','battery_in_cabinet','create_time',
        'open_time','agency_id','agency_name','channel_id','channel_name','city','area','street',
        'community','address','battery_product_id','battery_product','swap_fee_standard','is_swap',
        'is_sell_vehicle','cabinet_sn_list','income_items','indoor_outdoor','is_24h','open_apply_time',
        'open_applicant','open_approve_time','open_approver','open_delivery_time','open_delivery_person',
        'open_install_time','open_install_person','open_accept_time','open_accept_person','confirm_open_person',
        'total_sign_users','total_unsub_users','sign_users_30d','unsub_users_30d','sign_users_90d',
        'unsub_users_90d','swap_3d','swap_7d','swap_30d','swap_90d','total_swap_count','last_swap_time']

# 数值字段（转 int）
NUMERIC = {'cabinet_count','cabinet_offline_count','battery_in_cabinet','total_sign_users',
           'total_unsub_users','sign_users_30d','unsub_users_30d','sign_users_90d','unsub_users_90d',
           'swap_3d','swap_7d','swap_30d','swap_90d','total_swap_count'}

# CSV 头顺序（用于位置对齐校验）
EXPECT_CN = ['网点id','网点名称','网点标签','商户ID','商户名称','网点行业','收益人id','收益人姓名',
             '收益人手机号','独立电表状态','电费结算方式','电费结算周期','最近结算时间','联系人姓名',
             '联系人手机号','业务员id','业务员名称','审核状态','换电柜状态','换电柜数量','换电柜离线数量',
             '柜内电池数量','创建时间','开业时间','代理商id','代理商名称','渠道商id','渠道商名称','城市',
             '区域','街道','社区','详细地址','电池产品id','电池产品名称','换电收费标准','是否换电','是否售车',
             '换电柜sn','收入项','室内/室外','是否24小时','开业申请时间','开业申请人','开业审批时间',
             '开业审批人','开业送货完成时间','开业送货人','开业安装时间','开业安装人','开业验收时间',
             '开业验收人','确认开业人','累计签约用户数','累计退订用户数','近1个月签约用户数','近1个月退订用户数',
             '近3个月签约用户数','近3个月退订用户数','近3天换电次数','近7天换电次数','近1个月换电次数',
             '近3个月换电次数','总换电数','最后一次换电实际']


def to_int(v):
    v = (v or '').strip().replace(',', '')
    if v == '':
        return 0
    try:
        return int(float(v))
    except Exception:
        return 0


def main():
    print("读取 CSV:", CSVP)
    rows_out = []
    with open(CSVP, encoding='utf-8-sig', newline='') as f:
        r = csv.reader(f)
        header = next(r)
        # 位置对齐校验：前 3 列 + 城市(28) + 总换电数(63) 必须一致
        assert len(header) == len(EXPECT_CN) == len(KEYS), \
            "列数不一致 header=%d expect=%d keys=%d" % (len(header), len(EXPECT_CN), len(KEYS))
        for i in (0, 1, 28, 63):
            assert header[i] == EXPECT_CN[i], "位置 %d 期望 %s 实际 %s" % (i, EXPECT_CN[i], header[i])
        n = 0
        for row in r:
            if len(row) < len(KEYS):
                row = row + [''] * (len(KEYS) - len(row))
            rec = {}
            for i, k in enumerate(KEYS):
                v = row[i] if i < len(row) else ''
                rec[k] = to_int(v) if k in NUMERIC else (v.strip() if isinstance(v, str) else v)
            rows_out.append(rec)
            n += 1
    print("  CSV 解析完成：%d 行" % n)

    print("载入 dashboard_data.json ...")
    D = json.load(open(OUT, encoding='utf-8'))
    W = D.setdefault('site', {})
    old = len(W.get('detail') or [])
    W['detail'] = rows_out
    W['site_detail'] = rows_out
    W['site_total'] = n
    # total 保留为真实 DB 总量（11064），detail 为全量样本（10681）
    D['site'] = W
    print("  site.detail: %d → %d 行" % (old, n))

    json.dump(D, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print("DONE ->", OUT)


if __name__ == '__main__':
    main()
