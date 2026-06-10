"""Command-line interface for the banking assistant."""

from banking_agent.service import build_agent, run_agent


def main() -> None:
    """Start the interactive CLI chat loop."""
    print("=" * 60)
    print("  Banking Domain Agent  (powered by LangChain + Groq)")
    print("  Type 'exit' or 'quit' to stop.")
    print("=" * 60)

    agent = build_agent()

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        print("\nAgent thinking...\n")
        response = run_agent(agent, user_input)
        print(f"\nAgent: {response}\n")
        print("-" * 60)


if __name__ == "__main__":
    main()
