"""演示数据脚本：直接写入若干人员与活动，方便本机预览看板效果。"""

from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import Activity, Staff


async def seed() -> None:
    async with SessionLocal() as db:
        # 重复执行幂等：先清空既有 demo 数据，避免唯一键冲突。
        await db.execute(delete(Activity))
        await db.execute(delete(Staff))
        await db.flush()

        staff1 = Staff(name="李剑锐", role="销售", department="华北组")
        staff2 = Staff(name="肖俊", role="解决方案", department="华东组")
        staff3 = Staff(name="张伟", role="销售", department="行业组")
        db.add_all([staff1, staff2, staff3])
        await db.flush()

        activities = [
            Activity(staff_id=staff1.id, report_date=date(2026, 6, 4), activity_type="方案撰写", target="广州交研院", opportunity="广州交研院物流数据集项目", description="合规评审支撑，完成内部需求反馈澄清", confidence=0.9),
            Activity(staff_id=staff1.id, report_date=date(2026, 6, 4), activity_type="拜访客户", target="广州供电局", opportunity="广州供电局可视化系统", description="完成工作清单确认和修改，输入给交付团队评估成本", confidence=0.85),
            Activity(staff_id=staff1.id, report_date=date(2026, 6, 4), activity_type="商机跟进", target="海南大数据中心", opportunity="海南大数据中心地址项目", description="财评结果申诉中", confidence=0.9),
            Activity(staff_id=staff1.id, report_date=date(2026, 6, 4), activity_type="招投标", target="广州交研院", opportunity="广州交研院物流数据集项目", description="整体项目已挂网招标", confidence=0.95),
            Activity(staff_id=staff2.id, report_date=date(2026, 6, 5), activity_type="拜访客户", target="上海市大数据中心", opportunity="上海城市大脑二期", description="与技术部门沟通方案细节", confidence=0.9),
            Activity(staff_id=staff2.id, report_date=date(2026, 6, 5), activity_type="方案撰写", target="苏州工业园区", opportunity="苏州智慧园区平台", description="完成技术方案初稿", confidence=0.85),
            Activity(staff_id=staff3.id, report_date=date(2026, 6, 5), activity_type="渠道拓展", target="华为云", opportunity="", description="对接华为云生态合作部，沟通联合解决方案", confidence=0.8),
            Activity(staff_id=staff3.id, report_date=date(2026, 6, 6), activity_type="商机跟进", target="深圳公安局", opportunity="深圳智慧警务项目", description="提交POC方案，等待评审结果", confidence=0.9),
            Activity(staff_id=staff1.id, report_date=date(2026, 6, 8), activity_type="项目推进", target="广州数据集团", opportunity="广州数据产品上架", description="数据产品上架材料填报完成", confidence=0.85),
            Activity(staff_id=staff2.id, report_date=date(2026, 6, 8), activity_type="回款跟进", target="杭州规划局", opportunity="杭州规划一张图", description="催付验收尾款，对方承诺月底前支付", confidence=0.9),
        ]
        db.add_all(activities)
        await db.commit()

        total_staff = (await db.execute(select(Staff))).scalars().all()
        total_acts = (await db.execute(select(Activity))).scalars().all()
        print(f"✅ 插入 {len(total_staff)} 名人员，{len(total_acts)} 条活动记录")


if __name__ == "__main__":
    asyncio.run(seed())
