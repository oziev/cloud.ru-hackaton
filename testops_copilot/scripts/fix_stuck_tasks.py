#!/usr/bin/env python3
"""
Скрипт для исправления зависших задач в статусе 'optimization'
Обновляет их статус на 'failed' с сообщением об ошибке
"""

import sys
import os
from datetime import datetime

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.utils.database import get_db
from shared.models.database import Request
from shared.utils.logger import agent_logger

def fix_stuck_tasks():
    """Исправляет зависшие задачи в различных статусах"""
    try:
        with get_db() as db:
            from datetime import datetime, timedelta
            # Находим все задачи которые зависли более 10 минут назад
            timeout_threshold = datetime.utcnow() - timedelta(minutes=10)
            
            # Задачи в статусах которые не должны длиться долго
            stuck_statuses = ["pending", "processing", "started", "reconnaissance", "generation", "validation", "optimization"]
            
            stuck_tasks = db.query(Request).filter(
                Request.status.in_(stuck_statuses),
                Request.started_at < timeout_threshold
            ).all()
            
            # Также проверяем задачи без started_at но созданные более 10 минут назад
            old_pending = db.query(Request).filter(
                Request.status == "pending",
                Request.created_at < timeout_threshold,
                Request.started_at == None
            ).all()
            
            stuck_tasks.extend(old_pending)
            
            if not stuck_tasks:
                print("✅ Нет зависших задач")
                return
            
            print(f"🔍 Найдено {len(stuck_tasks)} зависших задач:")
            
            for task in stuck_tasks:
                old_status = task.status
                print(f"  - {task.request_id} (статус: {old_status}, создана: {task.created_at})")
                
                # Обновляем статус на 'failed'
                task.status = "failed"
                task.error_message = f"Задача зависла в статусе '{old_status}' более 10 минут. Автоматически завершена системой."
                task.completed_at = datetime.utcnow()
                
                agent_logger.warning(
                    f"Fixed stuck task {task.request_id}",
                    extra={
                        "request_id": str(task.request_id),
                        "old_status": old_status,
                        "new_status": "failed"
                    }
                )
            
            db.commit()
            print(f"✅ Обновлено {len(stuck_tasks)} задач")
            
    except Exception as e:
        agent_logger.error(f"Error fixing stuck tasks: {e}", exc_info=True)
        print(f"❌ Ошибка при исправлении задач: {e}")
        raise

if __name__ == "__main__":
    fix_stuck_tasks()

