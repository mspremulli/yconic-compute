import streamlit as st
import asyncio
import os
import threading
import subprocess
import time
from swarm.orchestrator import SwarmOrchestrator
from swarm.types.task import TaskType

st.set_page_config(page_title="Yconic Agent Swarm", page_icon="🧠")

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = None

if "results" not in st.session_state:
    st.session_state.results = {}

if "feedback" not in st.session_state:
    st.session_state.feedback = []

if "initialized" not in st.session_state:
    st.session_state.initialized = False

if "async_runner" not in st.session_state:
    st.session_state.async_runner = None


class AsyncRunner:
    def __init__(self):
        self.loop = None
        self.thread = None
        self.initialized = False
        
    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        
    def start(self):
        if not self.initialized:
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            self.initialized = True
            time.sleep(0.5)
            
    def run(self, coro):
        if not self.initialized:
            self.start()
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=300)


def run_gh_cmd(cmd):
    """Run a GitHub CLI command and return output"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def create_fix_branch(issue_description, repo_owner, repo_name):
    """Create a branch with a fix based on feedback"""
    
    # Create a branch name from timestamp
    branch_name = f"auto-fix/{int(time.time())}"
    
    # Get current branch
    success, current_branch, _ = run_gh_cmd("git branch --show-current")
    if not success:
        current_branch = "main"
    
    # Create new branch
    success, _, err = run_gh_cmd(f"git checkout -b {branch_name}")
    if not success:
        return None, f"Failed to create branch: {err}"
    
    # Create a fix file
    fix_content = f"""# Auto-generated fix from feedback

Issue reported: {issue_description}

This is an automated placeholder fix.
In a real implementation, the swarm would analyze the issue and generate actual code.

Timestamp: {time.time()}
"""
    
    with open("data/auto_fix.md", "w") as f:
        f.write(fix_content)
    
    # Add and commit
    run_gh_cmd("git add data/auto_fix.md")
    run_gh_cmd(f'git commit -m "Auto-fix: {issue_description[:50]}"')
    
    # Push branch
    success, _, err = run_gh_cmd(f"git push -u origin {branch_name}")
    if not success:
        return None, f"Failed to push: {err}"
    
    # Create PR
    pr_title = f"Auto-fix: {issue_description[:50]}"
    pr_body = f"""## Description
Auto-generated fix from swarm feedback system.

**Issue:** {issue_description}

**Timestamp:** {time.time()}

This PR was automatically created by the Yconic Agent Swarm.
"""
    
    success, pr_url, err = run_gh_cmd(
        f'gh pr create --title "{pr_title}" --body "{pr_body}" --base main'
    )
    
    # Switch back to original branch
    run_gh_cmd(f"git checkout {current_branch}")
    
    if success:
        return pr_url.strip(), None
    return None, f"Failed to create PR: {err}"


def save_feedback(task_id, rating, comment, repo_owner="", repo_name=""):
    """Save feedback and potentially create GitHub PR"""
    import json
    
    feedback_entry = {
        "timestamp": time.time(),
        "task_id": task_id,
        "rating": rating,
        "comment": comment,
    }
    
    # Save to file
    os.makedirs("data", exist_ok=True)
    with open("data/feedback.json", "a") as f:
        f.write(json.dumps(feedback_entry) + "\n")
    
    # If bad feedback and GitHub configured, create branch/PR
    pr_url = None
    if rating == "bad" and repo_owner and repo_name:
        issue_desc = comment or f"Task {task_id} failed"
        pr_url, error = create_fix_branch(issue_desc, repo_owner, repo_name)
        if error:
            feedback_entry["pr_error"] = error
    
    feedback_entry["pr_url"] = pr_url
    return feedback_entry


st.title("🧠 Yconic Agent Swarm")

with st.sidebar:
    st.header("Configuration")
    config_path = st.text_input("Config Path", value="./config/agents-fast.yaml")
    
    st.divider()
    st.subheader("GitHub Integration (Optional)")
    gh_repo = st.text_input("Repo (owner/repo)", placeholder="e.g., username/myproject")
    st.caption("When you mark feedback as 👎 Bad, we'll auto-create a fix branch!")
    
    if st.button("Initialize Swarm", type="primary"):
        with st.spinner("Initializing swarm (this may take a minute)..."):
            try:
                os.chdir("/home/yconic/Desktop/yconic_compute")
                st.session_state.async_runner = AsyncRunner()
                st.session_state.async_runner.start()
                
                st.session_state.orchestrator = SwarmOrchestrator.from_config(config_path)
                st.session_state.async_runner.run(st.session_state.orchestrator.initialize())
                st.session_state.initialized = True
                st.success("Swarm initialized!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    
    st.divider()
    st.subheader("Agents")
    if st.session_state.orchestrator:
        for name, agent in st.session_state.orchestrator.agents.items():
            st.text(f"• {name}: {agent.role} ({agent.state.value})")

    st.divider()
    st.subheader("💡 Autonomous Orgs")
    if st.button("View Framework"):
        with open("AUTONOMOUS_ORGS.md", "r") as f:
            st.markdown(f.read())

if st.session_state.initialized:
    task_type = st.selectbox(
        "Task Type",
        ["general", "code", "research", "analysis", "creative"],
        index=0
    )

    task_type_map = {
        "general": TaskType.GENERAL,
        "code": TaskType.CODE,
        "research": TaskType.RESEARCH,
        "analysis": TaskType.ANALYSIS,
        "creative": TaskType.CREATIVE,
    }

    task_description = st.text_area("Task Description", height=120, placeholder="What would you like the swarm to do?")

    if st.button("Submit Task", type="primary"):
        if task_description:
            with st.spinner("Swarm is working... (may take 10-30s)"):
                try:
                    runner = st.session_state.async_runner
                    task_id = runner.run(
                        st.session_state.orchestrator.receive_task(
                            task_description, 
                            task_type_map[task_type]
                        )
                    )
                    result = runner.run(st.session_state.orchestrator.execute(task_id))
                    st.session_state.results[task_id] = result
                    
                    st.success("✅ Task completed!")
                    st.subheader("Result")
                    st.write(result.final_answer or result.error)
                    st.info(f"Execution time: {result.execution_time_seconds:.2f}s | Success: {result.success}")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.warning("Please enter a task description")

    if st.session_state.results:
        st.divider()
        st.subheader("📜 History")
        
        # Show most recent first
        recent_items = list(st.session_state.results.items())[-3:][::-1]
        for tid, res in recent_items:
            with st.expander(f"Task: {tid[:8]}... ({res.execution_time_seconds:.1f}s)"):
                st.write(res.final_answer or res.error)
                
                # Feedback section
                st.markdown("**Was this helpful? Give feedback:**")
                
                # Get repo info
                gh_repo = st.session_state.get("gh_repo", "")
                repo_owner = ""
                repo_name = ""
                if "/" in gh_repo:
                    repo_owner, repo_name = gh_repo.split("/", 1)
                
                col1, col2, col3 = st.columns([1, 2, 2])
                with col1:
                    if st.button("👍 Good", key=f"good_{tid}"):
                        fb = save_feedback(tid, "good", "", repo_owner, repo_name)
                        st.session_state.feedback.append(fb)
                        st.success("Thanks for the feedback!")
                with col2:
                    if st.button("👎 Bad", key=f"bad_{tid}"):
                        fb = save_feedback(tid, "bad", "Auto-fix from bad feedback", repo_owner, repo_name)
                        st.session_state.feedback.append(fb)
                        if fb.get("pr_url"):
                            st.success("Branch & PR created!")
                            st.markdown(f"[View PR]({fb['pr_url']})")
                        elif fb.get("pr_error"):
                            st.error(f"Error: {fb['pr_error']}")
                        else:
                            st.info("Configure GitHub repo in sidebar to auto-create fixes!")
                with col3:
                    feedback_comment = st.text_input("Comment", key=f"comment_{tid}", placeholder="What could be improved?")
                    if feedback_comment:
                        fb = save_feedback(tid, "comment", feedback_comment, repo_owner, repo_name)
                        st.session_state.feedback.append(fb)
                        if fb.get("pr_url"):
                            st.success("Branch & PR created!")
                            st.markdown(f"[View PR]({fb['pr_url']})")
                        else:
                            st.success("Feedback saved!")

else:
    st.info("👈 Click **Initialize Swarm** in the sidebar to get started!")
    st.markdown("---")
    st.subheader("💡 About Autonomous Organizations")
    st.markdown("""
    This swarm demonstrates how AI agents can work together to complete tasks.
    
    For your hackathon, think about:
    - What if these agents had access to your company data?
    - What if they could make decisions on your behalf?
    - What tasks could be fully autonomous?
    
    Click **View Framework** in the sidebar for a complete framework on building autonomous organizations.
    """)
