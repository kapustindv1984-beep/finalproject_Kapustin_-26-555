"""Командный интерфейс ValutaTrade Hub."""
import shlex


def main() -> None:
    """Запускает цикл чтения команд пользователя."""
    print("ValutaTrade Hub. Введите 'help' для списка команд.")
    while True:
        try:
            raw = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("Bye!")
            break
        if not raw:
            continue
        command, *_args = shlex.split(raw)
        if command == "exit":
            print("Bye!")
            break
        print(f"Команда '{command}' пока не реализована")


if __name__ == "__main__":
    main()