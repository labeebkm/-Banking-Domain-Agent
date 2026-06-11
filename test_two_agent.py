"""Manual smoke test for the two-agent banking assistant."""

from banking_agent.service import build_two_agent_system, run_two_agent_system


def main() -> None:
    agent = build_two_agent_system()

    questions = [
        "What is KYC?",
        "What are the latest home loan rates from SBI?",
        "What are the latest RBI announcements?",
        "What is the capital of France?",
    ]

    for question in questions:
        print(f"\nQ: {question}")
        print(f"A: {run_two_agent_system(agent, question)}")
        print("-" * 60)


if __name__ == "__main__":
    main()
