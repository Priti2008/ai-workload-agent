import json
import os
from pathlib import Path

from dotenv import load_dotenv
import openai
from openai import OpenAI


DATA_PATH = Path(__file__).with_name("data.json")


def calculate_workload(member):
    """Return the available hours, assigned hours, and load ratio for a member."""
    available_hours = member["capacity_hours"] - member["meeting_hours"]
    if available_hours <= 0:
        raise ValueError(f"{member['name']} must have positive available hours")

    assigned_hours = sum(
        task["estimated_hours"] for task in member.get("assigned_tasks", [])
    )
    return {
        "available_hours": available_hours,
        "assigned_hours": assigned_hours,
        "load_ratio": assigned_hours / available_hours,
    }


def get_fallback_recommendations(overloaded, underloaded):
    """Create valid local task transfers when the OpenAI request is unavailable."""
    recommendations = []
    remaining_capacity = {
        member["name"]: member["available_hours"] - member["assigned_hours"]
        for member in underloaded
    }
    underloaded_index = 0

    for source in overloaded:
        for task in source.get("assigned_tasks", []):
            target_index = underloaded_index
            while (
                target_index < len(underloaded)
                and remaining_capacity[underloaded[target_index]["name"]]
                < task["estimated_hours"]
            ):
                target_index += 1
            if target_index >= len(underloaded):
                continue

            underloaded_index = target_index
            target = underloaded[target_index]
            recommendations.append(
                {
                    "from_member": source["name"],
                    "to_member": target["name"],
                    "task": task["title"],
                    "estimated_hours": task["estimated_hours"],
                }
            )
            remaining_capacity[target["name"]] -= task["estimated_hours"]
            if remaining_capacity[target["name"]] <= 0:
                underloaded_index += 1

    return recommendations


def get_recommendations(team_members, overloaded, underloaded):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_actual_openai_api_key_here":
        return get_fallback_recommendations(overloaded, underloaded)

    prompt = {
        "team_members": team_members,
        "overloaded_members": overloaded,
        "underloaded_members": underloaded,
        "request": (
            "Recommend practical task transfers from overloaded members to "
            "underloaded members. Only recommend existing tasks, and do not "
            "assign a task more than once. Return an array of objects with "
            "from_member, to_member, task, and estimated_hours."
        ),
    }
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a workload planning assistant. Return only valid "
                        "JSON matching the requested schema."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "task_recommendations",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "recommendations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "from_member": {"type": "string"},
                                        "to_member": {"type": "string"},
                                        "task": {"type": "string"},
                                        "estimated_hours": {"type": "number"},
                                    },
                                    "required": [
                                        "from_member",
                                        "to_member",
                                        "task",
                                        "estimated_hours",
                                    ],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["recommendations"],
                        "additionalProperties": False,
                    },
                },
            },
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        recommendations = parsed.get("recommendations")
        if not isinstance(recommendations, list):
            raise ValueError("OpenAI response did not contain a JSON array")
        return recommendations
    except (openai.RateLimitError, openai.APIError, openai.OpenAIError, ValueError):
        return get_fallback_recommendations(overloaded, underloaded)


def main():
    load_dotenv(Path(__file__).with_name(".env"))
    with DATA_PATH.open("r", encoding="utf-8") as data_file:
        data = json.load(data_file)

    overloaded = []
    underloaded = []
    for member in data["team_members"]:
        workload = calculate_workload(member)
        member.update(workload)
        if workload["load_ratio"] > 1.1:
            overloaded.append(member)
        elif workload["load_ratio"] < 0.6:
            underloaded.append(member)

    data["ai_recommendations"] = get_recommendations(
        overloaded=overloaded,
        underloaded=underloaded,
        team_members=data["team_members"],
    )
    with DATA_PATH.open("w", encoding="utf-8") as data_file:
        json.dump(data, data_file, indent=2)
        data_file.write("\n")


if __name__ == "__main__":
    main()

# ==========================================
# UI INTEGRATION WRAPPER (Add this at the bottom)
# ==========================================
def generate_rebalance_plan(raw_data):
    """Wrapper function to integrate friend's backend with app.py UI"""
    team_members = raw_data.get("team", raw_data.get("team_members", []))
    
    overloaded = []
    underloaded = []
    
    for member in team_members:
        # Field mapping (capacity_hours default 40)
        if "capacity_hours" not in member:
            member["capacity_hours"] = 40
            
        # Task field mapping
        for t in member.get("assigned_tasks", []):
            if "estimated_hours" not in t and "hours" in t:
                t["estimated_hours"] = t["hours"]
                
        try:
            workload = calculate_workload(member)
            member.update(workload)
            if workload["load_ratio"] > 1.1:
                overloaded.append(member)
            elif workload["load_ratio"] < 0.6:
                underloaded.append(member)
        except Exception:
            continue

    raw_recs = get_recommendations(team_members, overloaded, underloaded)
    
    # Format data to match app.py UI expectations
    formatted_reassignments = []
    for idx, rec in enumerate(raw_recs):
        formatted_reassignments.append({
            "task_id": f"TASK-{100 + idx + 1}",
            "task_title": rec.get("task", "Assigned Task"),
            "from_user": rec.get("from_member", "Unknown"),
            "to_user": rec.get("to_member", "Unknown"),
            "hours": rec.get("estimated_hours", 0),
            "reason": f"Optimized transfer to balance capacity between {rec.get('from_member')} and {rec.get('to_member')}."
        })
        
    return {
        "reassignments": formatted_reassignments,
        "projected_impact": "Workload successfully rebalanced across available team capacity."
    }