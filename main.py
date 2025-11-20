import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product, Order

app = FastAPI(title="Giftnama API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Helpers ----------
class ProductOut(Product):
    id: str


def serialize_product(doc) -> ProductOut:
    return ProductOut(
        id=str(doc.get("_id")),
        title=doc.get("title"),
        description=doc.get("description", ""),
        price=float(doc.get("price", 0)),
        category=doc.get("category"),
        tags=doc.get("tags", []),
        images=doc.get("images", []),
        rating=float(doc.get("rating", 0)),
        in_stock=bool(doc.get("in_stock", True)),
        stock_qty=int(doc.get("stock_qty", 0)),
    )


# ---------- Seed Demo Products (idempotent) ----------
@app.on_event("startup")
def seed_products():
    if db is None:
        return
    products_coll = db["product"]
    if products_coll.count_documents({}) == 0:
        demo = [
            {
                "title": "Rose Luxe Perfume Gift Set",
                "description": "An elegant duo of eau de parfum and travel spray in a velvet keepsake box.",
                "price": 89.0,
                "category": "Fragrances",
                "tags": ["perfume", "valentine", "luxury", "gift"],
                "images": [
                    {"url": "https://images.unsplash.com/photo-1611930022073-b7a4ba5fcccd", "alt": "Perfume bottle"}
                ],
                "rating": 4.9,
                "in_stock": True,
                "stock_qty": 120,
            },
            {
                "title": "Artisanal Chocolate Hamper",
                "description": "Curated Belgian chocolates with roasted nuts, sea salt caramels and truffles.",
                "price": 59.0,
                "category": "Gourmet",
                "tags": ["chocolate", "hamper", "birthday"],
                "images": [
                    {"url": "https://images.unsplash.com/photo-1541976076758-347942db1970", "alt": "Chocolate gift"}
                ],
                "rating": 4.7,
                "in_stock": True,
                "stock_qty": 80,
            },
            {
                "title": "Personalized Bamboo Organizer",
                "description": "Engraved desk organizer crafted from sustainable bamboo.",
                "price": 35.0,
                "category": "Personalized",
                "tags": ["desk", "bamboo", "personalized"],
                "images": [
                    {"url": "https://images.unsplash.com/photo-1524758631624-e2822e304c36", "alt": "Desk organizer"}
                ],
                "rating": 4.6,
                "in_stock": True,
                "stock_qty": 50,
            },
        ]
        products_coll.insert_many(demo)


# ---------- Routes ----------
@app.get("/")
def health():
    return {"message": "Giftnama API running"}


@app.get("/api/products", response_model=List[ProductOut])
def list_products(q: Optional[str] = None, category: Optional[str] = None):
    if db is None:
        # Return static demo if db not configured
        demo = [
            {
                "id": "1",
                "title": "Rose Luxe Perfume Gift Set",
                "description": "An elegant duo of eau de parfum and travel spray in a velvet keepsake box.",
                "price": 89.0,
                "category": "Fragrances",
                "tags": ["perfume", "valentine", "luxury", "gift"],
                "images": [
                    {"url": "https://images.unsplash.com/photo-1611930022073-b7a4ba5fcccd", "alt": "Perfume bottle"}
                ],
                "rating": 4.9,
                "in_stock": True,
                "stock_qty": 120,
            }
        ]
        return demo

    filter_dict = {}
    if q:
        filter_dict["title"] = {"$regex": q, "$options": "i"}
    if category:
        filter_dict["category"] = category

    docs = get_documents("product", filter_dict)
    return [serialize_product(d) for d in docs]


class AddProductRequest(Product):
    pass


@app.post("/api/products", response_model=str)
def add_product(payload: AddProductRequest):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    pid = create_document("product", payload)
    return pid


class CartItem(BaseModel):
    product_id: str
    quantity: int


class CheckoutRequest(BaseModel):
    items: List[CartItem]
    customer_name: str
    customer_email: str
    address_line1: str
    address_city: str
    address_state: str
    address_postal_code: str
    address_country: str = "US"


@app.post("/api/checkout", response_model=dict)
def checkout(payload: CheckoutRequest):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Fetch product snapshots and compute totals (mock if db missing)
    items_out = []
    subtotal = 0.0

    for item in payload.items:
        if db is None:
            # fallback single item mock
            price = 49.0
            title = "Gift Item"
            image = "https://images.unsplash.com/photo-1523275335684-37898b6baf30"
        else:
            try:
                doc = db["product"].find_one({"_id": ObjectId(item.product_id)})
                if not doc:
                    raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
                price = float(doc["price"])
                title = doc["title"]
                image = (doc.get("images") or [{}])[0].get("url")
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid product id")

        line_total = price * item.quantity
        subtotal += line_total
        items_out.append({
            "product_id": item.product_id,
            "title": title,
            "price": price,
            "quantity": item.quantity,
            "image": image,
            "line_total": round(line_total, 2)
        })

    shipping = 0 if subtotal >= 75 else 6.99
    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + shipping + tax, 2)

    # Persist order if db available
    if db is not None:
        order_doc = {
            "items": items_out,
            "subtotal": round(subtotal, 2),
            "shipping": round(shipping, 2),
            "tax": tax,
            "total": total,
            "customer": {
                "name": payload.customer_name,
                "email": payload.customer_email,
                "address_line1": payload.address_line1,
                "city": payload.address_city,
                "state": payload.address_state,
                "postal_code": payload.address_postal_code,
                "country": payload.address_country,
            },
            "status": "processing",
        }
        create_document("order", order_doc)

    return {
        "items": items_out,
        "subtotal": round(subtotal, 2),
        "shipping": round(shipping, 2),
        "tax": tax,
        "total": total,
        "status": "processing",
        "message": "Order placed successfully"
    }


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
