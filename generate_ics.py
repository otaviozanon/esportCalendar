import scrapling
import inspect

# Ver o que está disponível no módulo
print("📦 Conteúdo do módulo scrapling:")
print(dir(scrapling))
print("\n")

# Ver a documentação
print("📚 Docstring principal:")
print(scrapling.__doc__)
print("\n")

# Tentar ver exemplos de uso
for name in dir(scrapling):
    if not name.startswith('_'):
        obj = getattr(scrapling, name)
        if callable(obj):
            print(f"🔧 {name}:")
            try:
                sig = inspect.signature(obj)
                print(f"   Assinatura: {sig}")
            except:
                pass
            print(f"   Doc: {inspect.getdoc(obj)[:200] if inspect.getdoc(obj) else 'N/A'}")
            print()
