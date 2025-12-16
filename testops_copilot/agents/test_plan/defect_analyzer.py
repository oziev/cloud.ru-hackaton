
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from agents.test_plan.defect_integration import DefectIntegration
from shared.utils.logger import agent_logger
class DefectAnalyzer:
    def __init__(self):
        self.defect_integration = DefectIntegration()
    async def analyze_defect_history(
        self,
        project_key: str = None,
        days_back: int = 90,
        components: List[str] = None
    ) -> Dict[str, Any]:
        date_to = datetime.now().isoformat()
        date_from = (datetime.now() - timedelta(days=days_back)).isoformat()
        defects = await self.defect_integration.fetch_defects(
            project_key=project_key,
            date_from=date_from,
            date_to=date_to,
            source="all"
        )
        if components:
            defects = [
                d for d in defects
                if any(comp in d.get("affected_components", []) for comp in components)
            ]
        patterns = self.defect_integration.analyze_defect_patterns(defects)
        analysis = {
            "defects": defects,
            "patterns": patterns,
            "risk_areas": self.identify_risk_areas(defects, patterns),
            "trends": self._analyze_trends(defects),
            "recommendations": self._generate_recommendations(patterns, defects)
        }
        return analysis
    def identify_risk_areas(
        self,
        defects: List[Dict[str, Any]],
        patterns: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        if patterns is None:
            patterns = self.defect_integration.analyze_defect_patterns(defects)
        risk_areas = []
        component_risks = {}
        for defect in defects:
            components = defect.get("affected_components", [])
            priority = defect.get("priority", "medium")
            priority_weights = {
                "critical": 10,
                "blocker": 10,
                "high": 7,
                "medium": 4,
                "low": 2,
                "trivial": 1
            }
            weight = priority_weights.get(priority.lower(), 4)
            for component in components:
                if component not in component_risks:
                    component_risks[component] = {
                        "component": component,
                        "defect_count": 0,
                        "risk_score": 0,
                        "critical_defects": 0,
                        "recent_defects": 0
                    }
                component_risks[component]["defect_count"] += 1
                component_risks[component]["risk_score"] += weight
                if priority.lower() in ["critical", "blocker", "high"]:
                    component_risks[component]["critical_defects"] += 1
                created_at = defect.get("created_at")
                if created_at:
                    try:
                        defect_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        days_ago = (datetime.now() - defect_date.replace(tzinfo=None)).days
                        if days_ago <= 30:
                            component_risks[component]["recent_defects"] += 1
                    except:
                        pass
        for component, data in component_risks.items():
            max_possible_score = data["defect_count"] * 10
            normalized_score = min(100, (data["risk_score"] / max_possible_score * 100) if max_possible_score > 0 else 0)
            if normalized_score >= 70 or data["critical_defects"] >= 3:
                risk_level = "critical"
            elif normalized_score >= 50 or data["critical_defects"] >= 2:
                risk_level = "high"
            elif normalized_score >= 30 or data["defect_count"] >= 5:
                risk_level = "medium"
            else:
                risk_level = "low"
            risk_areas.append({
                "component": component,
                "defect_count": data["defect_count"],
                "risk_score": round(normalized_score, 2),
                "risk_level": risk_level,
                "critical_defects": data["critical_defects"],
                "recent_defects": data["recent_defects"]
            })
        risk_areas.sort(key=lambda x: x["risk_score"], reverse=True)
        return risk_areas
    def calculate_priority(
        self,
        test_info: Dict[str, Any],
        risk_areas: List[Dict[str, Any]] = None,
        defect_history: List[Dict[str, Any]] = None
    ) -> int:
        base_priority = 5
        test_component = test_info.get("component") or test_info.get("feature")
        if test_component and risk_areas:
            for risk_area in risk_areas:
                if risk_area["component"] == test_component:
                    risk_level = risk_area.get("risk_level", "low")
                    if risk_level == "critical":
                        base_priority += 3
                    elif risk_level == "high":
                        base_priority += 2
                    elif risk_level == "medium":
                        base_priority += 1
                    break
        if defect_history and test_component:
            critical_defects = [
                d for d in defect_history
                if test_component in d.get("affected_components", [])
                and d.get("priority", "").lower() in ["critical", "blocker"]
            ]
            if len(critical_defects) > 0:
                base_priority += min(2, len(critical_defects))
        test_severity = test_info.get("severity", "normal")
        if test_severity == "critical" or test_severity == "blocker":
            base_priority += 1
        elif test_severity == "minor" or test_severity == "trivial":
            base_priority -= 1
        priority = max(1, min(10, base_priority))
        return priority
    def _analyze_trends(self, defects: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not defects:
            return {
                "trend": "stable",
                "defects_per_week": 0,
                "critical_trend": "stable"
            }
        weekly_counts = {}
        weekly_critical = {}
        for defect in defects:
            created_at = defect.get("created_at")
            if not created_at:
                continue
            try:
                defect_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                week_key = defect_date.strftime("%Y-W%W")
                weekly_counts[week_key] = weekly_counts.get(week_key, 0) + 1
                priority = defect.get("priority", "").lower()
                if priority in ["critical", "blocker", "high"]:
                    weekly_critical[week_key] = weekly_critical.get(week_key, 0) + 1
            except:
                pass
        if len(weekly_counts) < 2:
            trend = "stable"
        else:
            sorted_weeks = sorted(weekly_counts.keys())
            recent_avg = sum(weekly_counts[w] for w in sorted_weeks[-4:]) / min(4, len(sorted_weeks))
            older_avg = sum(weekly_counts[w] for w in sorted_weeks[:-4]) / max(1, len(sorted_weeks) - 4) if len(sorted_weeks) > 4 else recent_avg
            if recent_avg > older_avg * 1.2:
                trend = "increasing"
            elif recent_avg < older_avg * 0.8:
                trend = "decreasing"
            else:
                trend = "stable"
        return {
            "trend": trend,
            "defects_per_week": round(sum(weekly_counts.values()) / max(1, len(weekly_counts)), 2),
            "critical_trend": "increasing" if len(weekly_critical) > 0 and max(weekly_critical.values()) > 2 else "stable"
        }
    def _generate_recommendations(
        self,
        patterns: Dict[str, Any],
        defects: List[Dict[str, Any]]
    ) -> List[str]:
        recommendations = []
        risk_areas = patterns.get("risk_areas", [])
        if risk_areas:
            top_risk = risk_areas[0]
            recommendations.append(
                f"Высокий приоритет тестирования для компонента '{top_risk['component']}': "
                f"{top_risk['defect_count']} дефектов, уровень риска {top_risk['risk_level']}"
            )
        critical_count = patterns.get("trends", {}).get("critical_count", 0)
        if critical_count > 0:
            recommendations.append(
                f"Обнаружено {critical_count} критических дефектов. "
                "Рекомендуется увеличить покрытие тестами для критических функций."
            )
        trends = self._analyze_trends(defects)
        if trends["trend"] == "increasing":
            recommendations.append(
                "Обнаружен рост количества дефектов. "
                "Рекомендуется провести регрессионное тестирование."
            )
        return recommendations