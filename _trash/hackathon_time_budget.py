"""AIY 黑客松实际可用开发时间计算
时间轴依据官方《AIY 黑客松·时间表》（AIY文件/markdown/AIY黑客松时间表.md）
场景：每晚只睡 6 小时，其余时间全部投入
"""
from datetime import datetime, timedelta

# (开始, 结束, 类别, 说明)
# 类别: opening=开幕式 design=设计 dev=开发 meal=吃饭 checkin=导师Check-in
#       roadshow_prep=路演材料 submit=整理提交 sleep=睡觉 free=自由支配(可用于开发)
T = [
    # Day0 8/3 周一（报到日，可选计入）
    ("2026-08-03 18:00", "2026-08-03 22:00", "free",  "周一晚（若提前到场）"),
    ("2026-08-03 22:00", "2026-08-04 08:00", "sleep", "周一晚睡觉窗口(10h)"),

    # Day1 8/4 周二
    ("2026-08-04 16:00", "2026-08-04 17:00", "opening", "开幕/确认命题"),
    ("2026-08-04 17:00", "2026-08-04 19:00", "design", "设计：定MVP/画流程/分工"),
    ("2026-08-04 19:00", "2026-08-04 20:00", "dev",    "搭骨架"),
    ("2026-08-04 20:00", "2026-08-04 22:00", "free",   "周二晚上段"),
    ("2026-08-04 22:00", "2026-08-05 08:00", "sleep",  "周二晚睡觉窗口(10h)"),

    # Day2 8/5 周三
    ("2026-08-05 08:00", "2026-08-05 09:00", "meal",   "早餐"),
    ("2026-08-05 09:00", "2026-08-05 12:00", "dev",    "核心开发"),
    ("2026-08-05 12:00", "2026-08-05 13:00", "meal",   "午餐"),
    ("2026-08-05 13:00", "2026-08-05 14:00", "checkin","导师中期Check-in"),
    ("2026-08-05 14:00", "2026-08-05 17:00", "dev",    "迭代联调"),
    ("2026-08-05 17:00", "2026-08-05 19:00", "roadshow_prep", "路演材料(视频/PPT)"),
    ("2026-08-05 19:00", "2026-08-05 20:00", "submit", "整理提交/微反思"),
    ("2026-08-05 20:00", "2026-08-05 22:00", "free",   "周三晚上段"),
    ("2026-08-05 22:00", "2026-08-06 08:00", "sleep",  "周三晚睡觉窗口(10h)"),

    # Day3 8/6 周四
    ("2026-08-06 08:00", "2026-08-06 08:00", "submit", "提交截止"),
]

SLEEP_HOURS_PER_NIGHT = 6   # 每晚压缩到 6 小时
INCLUDE_MONDAY = True        # 是否把周一（8/3 报到日）算进去

def hours(a, b):
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 3600

tot = {}
rows = []
for s, e, cat, label in T:
    if not INCLUDE_MONDAY and s < "2026-08-04":
        continue
    h = hours(s, e)
    if cat == "sleep":
        usable = h - SLEEP_HOURS_PER_NIGHT          # 睡觉窗口里，睡6h，剩余可用
        rows.append((label, h, f"睡 {SLEEP_HOURS_PER_NIGHT}h，挤出的可用 {usable:.0f}h"))
        tot["night_extra"] = tot.get("night_extra", 0) + max(usable, 0)
        tot["sleep"] = tot.get("sleep", 0) + SLEEP_HOURS_PER_NIGHT
    else:
        rows.append((label, h, cat))
        tot[cat] = tot.get(cat, 0) + h

scheduled_dev   = tot.get("dev", 0)
design          = tot.get("design", 0)
night_extra     = tot.get("night_extra", 0)
free_day        = tot.get("free", 0)
roadshow        = tot.get("roadshow_prep", 0)
overhead        = tot.get("opening", 0) + tot.get("meal", 0) + tot.get("checkin", 0) + tot.get("submit", 0)
sleep           = tot.get("sleep", 0)

total_dev  = scheduled_dev + night_extra + free_day          # 全部能写代码的时间
print("=" * 64)
print(f"{'时间段':<28}{'时长':>6}  类别")
print("-" * 64)
for label, h, cat in rows:
    print(f"{label:<28}{h:>5.0f}h  {cat}")
print("=" * 64)
print(f"比赛窗口总时长（含 8/3 晚）     : {sum(tot.values()):.0f}h")
print(f"睡觉（每晚 {SLEEP_HOURS_PER_NIGHT}h × 2 晚）   : {sleep:.0f}h")
print(f"固定消耗（开幕/吃饭/Checkin/提交）: {overhead:.0f}h")
print(f"路演材料（非开发，但必做）        : {roadshow:.0f}h")
print(f"设计（非编码，但算有效工作）      : {design:.0f}h")
print("-" * 64)
print(f"① 官方排定的开发时间            : {scheduled_dev:.0f}h")
print(f"② 夜晚压缩睡眠挤出的时间        : {night_extra:.0f}h")
print(f"③ 其他自由支配时间              : {free_day:.0f}h")
print(f"★ 可用于开发的总时间 = ①+②+③    : {total_dev:.0f}h")
print(f"★ 5 人并行总产能                : {total_dev*5:.0f} 人·小时")
print(f"★ 若周一不提前到场（去掉 8/3 晚）: 见下")

# 对照场景：不算周一
tot2_dev = scheduled_dev + (night_extra - (10-SLEEP_HOURS_PER_NIGHT)) + (free_day - 4)
print(f"  周一不到场时的开发总时间       : {tot2_dev:.0f}h（5人 {tot2_dev*5:.0f} 人·小时）")
