"""Genere les identifiants de l'espace d'administration.

    python -m deciban.admin_setup --email toi@exemple.com

Le mot de passe est affiche UNE FOIS et n'est jamais stocke en clair :
seule son empreinte part dans le fichier d'environnement.
"""

import argparse
import secrets
import string

from deciban.core.security import hash_password

#: Sans caracteres ambigus : ni l ni I ni O ni 0.
ALPHABET = "".join(c for c in string.ascii_letters + string.digits if c not in "lIO0")


def generate_password(length: int = 20) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="adresse de connexion")
    parser.add_argument(
        "--password",
        help="mot de passe choisi ; genere aleatoirement si absent",
    )
    args = parser.parse_args()

    password = args.password or generate_password()

    print()
    print("  Note ce mot de passe maintenant, il ne sera plus affiche :")
    print()
    print(f"      adresse      {args.email}")
    print(f"      mot de passe {password}")
    print()
    print("  Ajoute ces trois lignes au .env du serveur :")
    print()
    print(f"ADMIN_EMAIL={args.email}")
    print(f"ADMIN_PASSWORD_HASH={hash_password(password)}")
    print(f"SECRET_KEY={secrets.token_urlsafe(48)}")
    print()


if __name__ == "__main__":
    main()
