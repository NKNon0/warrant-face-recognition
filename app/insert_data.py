import asyncio
import json
import os
import tempfile
from dotenv import load_dotenv
from app.db import get_connection
from app.face_utils import get_face_embedding

load_dotenv()


async def insert_face_profile(
    person_name: str,
    image_path: str,
    source: str = "manual",
    id_number: str = None,
    detail: str = None,
    station: str = None,
    court: str = None,
    photo_url: str = None,
):
    """
    Insert a face profile with full metadata into face_profiles table.
    """
    embedding = get_face_embedding(image_path)
    if embedding is None:
        raise RuntimeError("DeepFace is not available or cannot compute embedding.")

    embedding_json = json.dumps(
        embedding.tolist() if hasattr(embedding, "tolist") else embedding
    )

    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO face_profiles
                   (person_name, id_number, detail, station, court, source, face_embedding, photo_url, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    person_name,
                    id_number,
                    detail,
                    station,
                    court,
                    source,
                    embedding_json,
                    photo_url,
                    json.dumps({"image": image_path}),
                ),
            )
            return cur.lastrowid


async def insert_license_plate(plate_text: str, image_path: str, metadata: dict = None):
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO license_plates (plate_text, plate_image_url, metadata) VALUES (%s, %s, %s)",
                (plate_text, image_path, json.dumps(metadata or {})),
            )
            return cur.lastrowid


async def insert_id_card(
    id_number: str, name: str, image_path: str, metadata: dict = None
):
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO id_cards (id_number, name, birthdate, address, card_image_url, metadata) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    id_number,
                    name,
                    None,
                    None,
                    image_path,
                    json.dumps(metadata or {}),
                ),
            )
            return cur.lastrowid


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Insert reference data into Face_Ai database."
    )
    subparsers = parser.add_subparsers(dest="command")

    parser_face = subparsers.add_parser("face", help="Insert face profile")
    parser_face.add_argument("person_name")
    parser_face.add_argument("image_path")
    parser_face.add_argument("--id-number", default=None)
    parser_face.add_argument("--detail", default=None)
    parser_face.add_argument("--station", default=None)
    parser_face.add_argument("--court", default=None)
    parser_face.add_argument("--photo-url", default=None)

    parser_plate = subparsers.add_parser("plate", help="Insert license plate data")
    parser_plate.add_argument("plate_text")
    parser_plate.add_argument("image_path")

    parser_id = subparsers.add_parser("id", help="Insert id card data")
    parser_id.add_argument("id_number")
    parser_id.add_argument("name")
    parser_id.add_argument("image_path")

    args = parser.parse_args()

    async def main():
        if args.command == "face":
            rid = await insert_face_profile(
                args.person_name,
                args.image_path,
                id_number=args.id_number,
                detail=args.detail,
                station=args.station,
                court=args.court,
                photo_url=args.photo_url,
            )
            print("Inserted face profile id=", rid)
        elif args.command == "plate":
            rid = await insert_license_plate(args.plate_text, args.image_path)
            print("Inserted license plate id=", rid)
        elif args.command == "id":
            rid = await insert_id_card(args.id_number, args.name, args.image_path)
            print("Inserted id card id=", rid)
        else:
            parser.print_help()

    asyncio.run(main())
