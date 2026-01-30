import asyncio
import os
import sys

# Add the project directory to sys.path to import modules
sys.path.append('/home/mateus/Projetcs/api-sgp')

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from base import engine
from maquinas.schema import Machine

async def seed_data():
    async with AsyncSession(engine) as session:
        # Check if we already have machines
        result = await session.exec(select(Machine))
        if len(result.all()) > 0:
            print("Machines already exist.")
            return

        print("Seeding machines...")
        machines = [
            Machine(name="Impressora Roland", active=True),
            Machine(name="Impressora Epson", active=True),
            Machine(name="Corte Laser", active=True),
            Machine(name="Calandra", active=True),
        ]
        session.add_all(machines)
        await session.commit()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(seed_data())
