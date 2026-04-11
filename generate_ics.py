import scrapling
import inspect

print("📦 Conteúdo do módulo scrapling:")
print(dir(scrapling))
print("\n")

for name in dir(scrapling):
    if not name.startswith('_'):
        try:
            obj = getattr(scrapling, name)
            if callable(obj):
                print(f"🔧 {name}")
        except:
            pass
