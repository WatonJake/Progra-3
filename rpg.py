from fastapi import FastAPI, Depends
from sqlalchemy import Column, Integer, String, ForeignKey, Table, create_engine, select, delete, func
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

# Configuración de la base de datos
SQLALCHEMY_DATABASE_URL = "sqlite:///./rpg.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Relaciones muchos a muchos con orden
from sqlalchemy import MetaData
metadata = MetaData()
personaje_mision = Table(
    'personaje_mision', Base.metadata,
    Column('personaje_id', ForeignKey('personajes.id'), primary_key=True),
    Column('mision_id', ForeignKey('misiones.id'), primary_key=True),
    Column('orden', Integer)
)

# Modelos
class Personaje(Base):
    __tablename__ = 'personajes'
    id = Column(Integer, primary_key=True)
    nombre = Column(String)
    xp = Column(Integer, default=0)
    misiones = relationship("Mision", secondary=personaje_mision)

class Mision(Base):
    __tablename__ = 'misiones'
    id = Column(Integer, primary_key=True)
    descripcion = Column(String)
    recompensa_xp = Column(Integer)

# Crear tablas
Base.metadata.create_all(bind=engine)

# App FastAPI
app = FastAPI()

# Endpoints
@app.post("/personajes")
def crear_personaje(nombre: str, db: Session = Depends(get_db)):
    nuevo = Personaje(nombre=nombre)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return {"id": nuevo.id, "nombre": nuevo.nombre, "xp": nuevo.xp}

@app.post("/misiones")
def crear_mision(descripcion: str, recompensa_xp: int, db: Session = Depends(get_db)):
    nueva = Mision(descripcion=descripcion, recompensa_xp=recompensa_xp)
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return {"id": nueva.id, "descripcion": nueva.descripcion, "recompensa_xp": nueva.recompensa_xp}

@app.post("/personajes/{id_personaje}/misiones/{id_mision}")
def aceptar_mision(id_personaje: int, id_mision: int, db: Session = Depends(get_db)):
    orden_actual = db.execute(
        select(func.count()).select_from(personaje_mision).where(personaje_mision.c.personaje_id == id_personaje)
    ).scalar()
    db.execute(personaje_mision.insert().values(
        personaje_id=id_personaje, mision_id=id_mision, orden=orden_actual
    ))
    db.commit()
    return {"msg": "Mision encolada"}

@app.post("/personajes/{id_personaje}/completar")
def completar_mision(id_personaje: int, db: Session = Depends(get_db)):
    result = db.execute(
        select(personaje_mision).where(personaje_mision.c.personaje_id == id_personaje).order_by(personaje_mision.c.orden).limit(1)
    ).fetchone()
    if not result:
        return {"msg": "Sin misiones"}

    mision_id = result.mision_id
    mision = db.query(Mision).get(mision_id)
    personaje = db.query(Personaje).get(id_personaje)
    personaje.xp += mision.recompensa_xp

    db.execute(delete(personaje_mision).where(
        (personaje_mision.c.personaje_id == id_personaje) &
        (personaje_mision.c.mision_id == mision_id)
    ))
    db.commit()
    return {"msg": f"Mision completada: {mision.descripcion}", "xp_total": personaje.xp}

@app.get("/personajes/{id_personaje}/misiones")
def listar_misiones(id_personaje: int, db: Session = Depends(get_db)):
    results = db.execute(
        select(Mision.descripcion).select_from(Mision)
        .join(personaje_mision, Mision.id == personaje_mision.c.mision_id)
        .where(personaje_mision.c.personaje_id == id_personaje)
        .order_by(personaje_mision.c.orden)
    ).fetchall()
    return [r[0] for r in results]