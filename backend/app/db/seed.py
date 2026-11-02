"""Synthetic demo data only. Requires --demo and DEMO_PASSWORD; never run on live data."""
import asyncio
import argparse
import os
from datetime import datetime, timezone
from sqlalchemy import select, text
from app.db.base import AsyncSessionLocal, Base
import app.db.models  # Register every relationship for standalone CLI execution.
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.models.university import University
from app.models.accommodation import Accommodation
from app.models.review import Review
from app.core.security import get_password_hash
import random
import json

# ─── Data ─────────────────────────────────────────────────────────────────────

UNIVERSITY = {
    "name": "Sol Plaatje University",
    "domain": "spu.ac.za",
    "province": "Northern Cape",
    "lat": -28.748199,
    "lng": 24.7650716,
}

LANDLORDS = [
    {"name": "Sea Of Mountains"},
    {"name": "Long Street Lofts"},
    {"name": "Moroka Hall"},
    {"name": "Tauna Hall"},
    {"name": "Mhudi Hall"},
    {"name": "Ra-Thaga Hall"},
    {"name": "Kimberley Student Nest"},
    {"name": "Diamond City Residences"},
]

STUDENTS = [
    {"name": "Thabo Nkosi"},
    {"name": "Lerato Mokoena"},
    {"name": "Sipho Dlamini"},
    {"name": "Nomvula Zulu"},
    {"name": "Kagiso Sithole"},
    {"name": "Ayanda Khumalo"},
    {"name": "Tshepiso Molefe"},
    {"name": "Rethabile Ntuli"},
    {"name": "Keabetswe Motsepe"},
    {"name": "Zanele Mahlangu"},
]

ACCOMMODATIONS = [
    {
        "title": "Sea Of Mountains",
        "address": "41 Lawson St, Labram, Kimberley, 8301",
        "lat": -28.74925037588339,
        "lng": 24.763082781954612,
        "price_min": 3200,
        "price_max": 4500,
        "description": "Sea Of Mountains offers modern, fully furnished student accommodation just minutes from Sol Plaatje University. Each unit features high-speed WiFi, a private bathroom, and 24/7 security. The communal study areas and kitchen facilities make it ideal for focused academic life.",
        "landlord_idx": 0,
    },
    {
        "title": "Long Street Lofts",
        "address": "102 Long Street, Albertynshof, Kimberley, 8301",
        "lat": -28.743968435524454,
        "lng": 24.751211412347107,
        "price_min": 2800,
        "price_max": 3800,
        "description": "Long Street Lofts provides affordable, comfortable student living in the heart of Albertynshof. The property features spacious rooms, reliable electricity and water supply, and a secure parking area. Walking distance to public transport routes serving SPU campus.",
        "landlord_idx": 1,
    },
    {
        "title": "Moroka Hall",
        "address": "26 Scanlan St, Labram, Kimberley, 8301",
        "lat": -28.748303,
        "lng": 24.765031,
        "price_min": 2500,
        "price_max": 3500,
        "description": "Moroka Hall is a well-established student residence offering single and shared rooms. Located in the quiet Labram area, residents enjoy a peaceful study environment, communal lounge, and laundry facilities. The hall has a strong community atmosphere among students.",
        "landlord_idx": 2,
    },
    {
        "title": "Tauna Hall",
        "address": "Sol Plaatje University South Campus, Birbeck Avenue, Labram, Kimberley, 8301",
        "lat": -28.755499669062736,
        "lng": 24.75999396761747,
        "price_min": 3000,
        "price_max": 4000,
        "description": "Tauna Hall is situated on the SPU South Campus, making it the most conveniently located student accommodation available. Residents have direct access to campus facilities including the library and sports grounds. Rooms are neat, secure, and include all basic utilities.",
        "landlord_idx": 3,
    },
    {
        "title": "Mhudi Hall",
        "address": "124 Du Toitspan Rd, Civic Centre, Kimberley, 8300",
        "lat": -28.743333683912415,
        "lng": 24.770438227582122,
        "price_min": 2600,
        "price_max": 3600,
        "description": "Mhudi Hall offers student accommodation along the busy Du Toitspan Road corridor with easy access to taxis and buses to campus. The property features a secured entrance, backup water storage, and an on-site caretaker. Suitable for both first and second year students.",
        "landlord_idx": 4,
    },
    {
        "title": "Ra-Thaga Hall",
        "address": "35 Edwards Rd, Kimberley, 8300",
        "lat": -28.73857704458885,
        "lng": 24.76735702758198,
        "price_min": 2900,
        "price_max": 3900,
        "description": "Ra-Thaga Hall is a popular choice among SPU students for its well-maintained rooms and responsive management. The property offers fibre internet connectivity, regular cleaning of common areas, and a strict visitor policy that maintains a safe living environment.",
        "landlord_idx": 5,
    },
    {
        "title": "Kimberley Student Nest",
        "address": "18 Phipson Street, Kimberley, 8301",
        "lat": -28.7412,
        "lng": 24.7598,
        "price_min": 2400,
        "price_max": 3200,
        "description": "Kimberley Student Nest is an affordable option for budget-conscious students. The property offers clean, basic rooms with shared bathrooms and kitchen. Security is provided by a perimeter wall and locked gate. Close to several supermarkets and a pharmacy.",
        "landlord_idx": 6,
    },
    {
        "title": "Diamond City Residences",
        "address": "7 Lennox Street, Kimberley, 8301",
        "lat": -28.7389,
        "lng": 24.7712,
        "price_min": 3800,
        "price_max": 5500,
        "description": "Diamond City Residences is a premium student accommodation option offering fully furnished en-suite rooms. The property features fibre WiFi, a rooftop study deck, backup generator, and 24/7 security personnel. One of the most modern student residences in Kimberley.",
        "landlord_idx": 7,
    },
    {
        "title": "Ubuntu House",
        "address": "55 Barkly Road, Kimberley, 8301",
        "lat": -28.7445,
        "lng": 24.7534,
        "price_min": 2200,
        "price_max": 3000,
        "description": "Ubuntu House promotes community living among students. Shared rooms and communal spaces encourage collaboration and support. The property is close to the Kimberley CBD and has reliable public transport connections to SPU. Meals can be arranged for an additional fee.",
        "landlord_idx": 0,
    },
    {
        "title": "Plateau View Apartments",
        "address": "33 Memorial Road, Kimberley, 8301",
        "lat": -28.7501,
        "lng": 24.7623,
        "price_min": 3400,
        "price_max": 4800,
        "description": "Plateau View Apartments offers spacious self-contained units for students who prefer more independence. Each unit has its own kitchenette, bathroom, and study nook. The property has fibre internet and covered parking. Suitable for postgraduate students and couples.",
        "landlord_idx": 1,
    },
    {
        "title": "Northgate Student Lodge",
        "address": "12 Dalham Road, Kimberley, 8301",
        "lat": -28.7358,
        "lng": 24.7689,
        "price_min": 2700,
        "price_max": 3500,
        "description": "Northgate Student Lodge is situated in a quiet northern suburb of Kimberley. The lodge offers single rooms with shared facilities. Management is responsive and maintenance requests are attended to promptly. A shuttle service to campus is available on weekday mornings.",
        "landlord_idx": 2,
    },
    {
        "title": "Campus Edge Rooms",
        "address": "9 Lawson Street, Labram, Kimberley, 8301",
        "lat": -28.7478,
        "lng": 24.7641,
        "price_min": 3100,
        "price_max": 4200,
        "description": "Campus Edge Rooms lives up to its name by being one of the closest privately-owned accommodations to SPU. Students can walk to lectures in under ten minutes. The property has recently been renovated and offers modern amenities including solar water heating.",
        "landlord_idx": 3,
    },
    {
        "title": "Galeshewe Gardens",
        "address": "88 Lewitton Street, Galeshewe, Kimberley, 8345",
        "lat": -28.7612,
        "lng": 24.7423,
        "price_min": 1800,
        "price_max": 2600,
        "description": "Galeshewe Gardens offers the most affordable student accommodation in the greater Kimberley area. Located in the Galeshewe township, the property is well-connected via taxis to SPU. Rooms are clean and secure. Ideal for students on NSFAS funding.",
        "landlord_idx": 4,
    },
    {
        "title": "Central Park Flats",
        "address": "45 Jones Street, Kimberley, 8301",
        "lat": -28.7423,
        "lng": 24.7667,
        "price_min": 3000,
        "price_max": 4100,
        "description": "Central Park Flats offers well-positioned student accommodation in central Kimberley. The building is fully secured with CCTV and access control. Each flat has a dedicated study area and the property includes a communal gym and outdoor braai area.",
        "landlord_idx": 5,
    },
    {
        "title": "Riviera Student Quarters",
        "address": "21 Riviera Road, Kimberley, 8301",
        "lat": -28.7534,
        "lng": 24.7589,
        "price_min": 2900,
        "price_max": 3900,
        "description": "Riviera Student Quarters provides comfortable accommodation in a safe, well-lit area. The property is managed by a full-time resident caretaker. Students benefit from reliable electricity, fast WiFi, and a quiet neighbourhood suitable for studying.",
        "landlord_idx": 6,
    },
    {
        "title": "Prospect Heights",
        "address": "67 Prospect Road, Kimberley, 8301",
        "lat": -28.7467,
        "lng": 24.7712,
        "price_min": 3300,
        "price_max": 4600,
        "description": "Prospect Heights is a modern student apartment complex offering fully furnished units. Amenities include fibre WiFi, backup power, a communal study room, and secure parking. The property management team is highly responsive and professional.",
        "landlord_idx": 7,
    },
    {
        "title": "Harmony House",
        "address": "14 Market Street, Kimberley, 8301",
        "lat": -28.7389,
        "lng": 24.7634,
        "price_min": 2500,
        "price_max": 3400,
        "description": "Harmony House is a student-focused property that prioritises a peaceful living environment. The property has a strict no-noise policy after 22:00. Rooms are well-maintained, and the caretaker conducts weekly inspections. Good water pressure and reliable electricity.",
        "landlord_idx": 0,
    },
    {
        "title": "Sunrise Cottages",
        "address": "3 Sunrise Street, Kimberley, 8301",
        "lat": -28.7512,
        "lng": 24.7556,
        "price_min": 2300,
        "price_max": 3100,
        "description": "Sunrise Cottages offers small but cozy self-contained units suitable for independent students. Each cottage has its own entrance, kitchenette, and bathroom. The property is walled and gated. A short taxi ride or bicycle trip to campus.",
        "landlord_idx": 1,
    },
    {
        "title": "The Bungalow",
        "address": "78 Schmidtsdrift Road, Kimberley, 8301",
        "lat": -28.7323,
        "lng": 24.7578,
        "price_min": 2600,
        "price_max": 3500,
        "description": "The Bungalow is a charming student accommodation option with a home-away-from-home feel. The landlord lives on the property and ensures everything runs smoothly. Includes WiFi, DSTV in the communal lounge, and a lush garden for relaxation.",
        "landlord_idx": 2,
    },
    {
        "title": "Highveld Residences",
        "address": "29 Highveld Drive, Kimberley, 8301",
        "lat": -28.7556,
        "lng": 24.7489,
        "price_min": 3200,
        "price_max": 4400,
        "description": "Highveld Residences is a well-established student accommodation block offering single and double rooms. The property has 24-hour security, a communal kitchen, and laundry facilities. Known for its strong student community and active social calendar.",
        "landlord_idx": 3,
    },
    {
        "title": "Kalahari Corner",
        "address": "51 Oliver Street, Kimberley, 8301",
        "lat": -28.7445,
        "lng": 24.7801,
        "price_min": 2700,
        "price_max": 3700,
        "description": "Kalahari Corner is named after the iconic landscape of the Northern Cape. This student accommodation offers clean, affordable rooms with basic amenities. The property is within easy reach of campus via public transport and has a safe, gated compound.",
        "landlord_idx": 4,
    },
    {
        "title": "Dingaan's Place",
        "address": "6 Egerton Road, Kimberley, 8301",
        "lat": -28.7367,
        "lng": 24.7723,
        "price_min": 2400,
        "price_max": 3200,
        "description": "Dingaan's Place is a budget-friendly student accommodation known for its friendly atmosphere. Rooms are basic but clean, and the landlord is approachable and fair. Suitable for first-year students looking for affordable options close to transport routes.",
        "landlord_idx": 5,
    },
    {
        "title": "Monument View Lodge",
        "address": "19 Monument Road, Kimberley, 8301",
        "lat": -28.7489,
        "lng": 24.7812,
        "price_min": 3500,
        "price_max": 5000,
        "description": "Monument View Lodge is a premium student accommodation option with stunning views of the Kimberley CBD. Rooms are spacious and fully furnished. The property features fibre WiFi, backup generator, CCTV, and an on-site gym.",
        "landlord_idx": 6,
    },
    {
        "title": "Tranquil Gardens",
        "address": "37 Garden Road, Kimberley, 8301",
        "lat": -28.7578,
        "lng": 24.7634,
        "price_min": 2800,
        "price_max": 3800,
        "description": "Tranquil Gardens lives up to its name with beautiful garden surroundings and a calm atmosphere. The property offers single rooms and shared flats. Ideal for students who value a quiet, natural environment for studying. Good water and electricity supply.",
        "landlord_idx": 7,
    },
    {
        "title": "Kimberley Heights",
        "address": "84 Bishops Avenue, Kimberley, 8301",
        "lat": -28.7412,
        "lng": 24.7556,
        "price_min": 3100,
        "price_max": 4300,
        "description": "Kimberley Heights offers elevated student accommodation with modern facilities. The property has recently undergone renovations and now features new bathrooms, a communal kitchen, and improved security. Management is professional and maintenance turnaround is quick.",
        "landlord_idx": 0,
    },
    {
        "title": "Stardust Residence",
        "address": "11 Stellar Street, Kimberley, 8301",
        "lat": -28.7534,
        "lng": 24.7712,
        "price_min": 2900,
        "price_max": 4000,
        "description": "Stardust Residence is a well-loved student property offering comfortable rooms at competitive prices. The property has 24-hour access control, a communal study room, and regular pest control. Known for its clean communal bathrooms and responsive management.",
        "landlord_idx": 1,
    },
    {
        "title": "Meadowlands Flats",
        "address": "62 Meadow Lane, Kimberley, 8301",
        "lat": -28.7456,
        "lng": 24.7489,
        "price_min": 2500,
        "price_max": 3400,
        "description": "Meadowlands Flats is a no-frills student accommodation option that delivers on the basics. Clean rooms, reliable utilities, and affordable pricing make it popular with NSFAS students. The property is near a shopping centre and has good taxi access.",
        "landlord_idx": 2,
    },
    {
        "title": "Cornerstone Lodge",
        "address": "5 Warren Street, Kimberley, 8301",
        "lat": -28.7489,
        "lng": 24.7601,
        "price_min": 3000,
        "price_max": 4200,
        "description": "Cornerstone Lodge is a solidly managed student property with a reputation for reliability. The property has been running for over a decade and has built a loyal student base. Features include WiFi, secure parking, and a communal braai area.",
        "landlord_idx": 3,
    },
    {
        "title": "Sunstone Apartments",
        "address": "48 Sunstone Avenue, Kimberley, 8301",
        "lat": -28.7523,
        "lng": 24.7667,
        "price_min": 3400,
        "price_max": 4800,
        "description": "Sunstone Apartments is a newer student accommodation development offering modern, fully equipped apartments. Each unit has its own kitchenette, bathroom, and fast fibre WiFi. The complex has biometric access control and covered parking bays.",
        "landlord_idx": 4,
    },
    {
        "title": "Labram Heights",
        "address": "73 Labram Road, Labram, Kimberley, 8301",
        "lat": -28.7501,
        "lng": 24.7645,
        "price_min": 2700,
        "price_max": 3700,
        "description": "Labram Heights is perfectly positioned in the Labram neighbourhood, closest to SPU campus. Students can walk to lectures in under 15 minutes. The property offers clean single rooms, a communal kitchen, and a secure yard. Very popular with SPU first years.",
        "landlord_idx": 5,
    },
]

REVIEW_TEMPLATES = [
    # Positive reviews
    ("positive", [
        "I have been staying at {name} for two semesters now and I have nothing but good things to say. The WiFi is fast and reliable, which is essential for submitting assignments online. The management is quick to respond to any maintenance issues and the overall cleanliness of the property is maintained at a high standard. I would definitely recommend this place to any SPU student looking for a comfortable stay.",
        "Living at {name} has been a great experience overall. The rooms are spacious and well ventilated. The landlord is very approachable and always available when you need something fixed. Security is taken seriously here with a guard at the gate every night. The water and electricity have never been cut while I have been staying here. Value for money is excellent.",
        "I chose {name} after visiting several places and it was the right decision. The location is convenient for catching taxis to campus and the neighbourhood feels safe. My room is clean and the furniture is in good condition. The other students staying here are friendly and we have formed a good community. The study area is quiet enough to focus on work.",
        "The accommodation at {name} exceeded my expectations. For the price I pay monthly, the facilities are excellent. There is always hot water, the internet works well, and maintenance requests are handled within a day or two. The landlord conducted an orientation when I first moved in which I appreciated. I feel safe and comfortable here.",
        "This is my second year at {name} and I renewed my lease without hesitation. The property is well-maintained and the management team is professional. I especially appreciate the backup water tank they installed last year which means we never run dry. WiFi could be slightly faster during peak hours but it is still usable. Overall a solid choice for SPU students.",
    ]),
    # Negative reviews
    ("negative", [
        "I had high hopes for {name} but the reality has been disappointing. The WiFi is slow and often disconnects during important online classes. Maintenance requests take weeks to be addressed. The communal bathrooms are not cleaned regularly enough. I have raised these concerns multiple times but nothing changes. The price does not reflect the quality of what is offered here.",
        "My stay at {name} has been stressful. The area does not feel safe at night and the security measures are inadequate. There is only one lock on the gate and the perimeter wall has gaps. I have had personal items go missing from the communal kitchen. The landlord is difficult to reach and dismissive when you do manage to contact them. Would not recommend.",
        "The electricity situation at {name} is a serious problem. Load shedding is bad enough but the property has no backup generator or solar, so we lose power for hours every day. The WiFi goes down with the power too. As a student I rely heavily on electricity and internet for my studies. This has negatively affected my academic performance. Management does not seem to care.",
        "I moved out of {name} after one semester because conditions were not acceptable. The plumbing was problematic with low water pressure and occasional no water days. The place was not properly cleaned before I moved in. The landlord was friendly at first but became unresponsive once the lease was signed. There are much better options available for the same price in Kimberley.",
        "The noise levels at {name} are unbearable. Other residents play loud music late into the night and there are no rules enforced about quiet hours. I complained to management several times and was told to sort it out myself. As someone studying for exams this was extremely disruptive. The rooms themselves are decent but the environment makes it impossible to study.",
    ]),
    # Neutral/mixed reviews
    ("neutral", [
        "My experience at {name} has been mixed. The room itself is fine and the price is reasonable. However the WiFi is inconsistent and the hot water only works well in the mornings. The landlord is polite but slow to act on maintenance issues. The location is convenient for campus. Overall it is an average place to stay. There are better options if you can afford them but it serves its purpose.",
        "Living at {name} is okay for the price. Nothing exceptional but nothing terribly wrong either. The basic utilities work most of the time. The security could be better. The landlord responds within a few days when you contact them. I have had better accommodation experiences in the past but this one is manageable for a student on a budget. Would probably consider alternatives before renewing.",
        "The accommodation at {name} is decent but has room for improvement. The rooms are adequately sized and the furniture is functional. WiFi works during the day but slows down in the evenings when everyone is online. Maintenance is handled but not urgently. The area is reasonably safe. Overall a satisfactory option for students who prioritise location and price over luxury.",
    ]),
]


async def seed(*, demo=False, password=None, session_factory=None):
    """Populate an empty demo database; never repair or backfill live reviews."""
    if not demo:
        raise RuntimeError("Demo seeding requires the explicit --demo flag.")
    if not isinstance(password, str) or not 8 <= len(password) <= 64 or len(password.encode("utf-8")) > 72:
        raise RuntimeError("Set DEMO_PASSWORD to 8-64 characters, at most 72 UTF-8 bytes.")
    factory = session_factory or AsyncSessionLocal
    rng = random.Random(42)
    verified_at = datetime.now(timezone.utc)
    async with factory() as db:
        async with db.begin():
            # Concurrent demo seed commands cannot both pass the empty check.
            await db.execute(text("SELECT pg_advisory_xact_lock(193734, 0)"))
            for table in Base.metadata.sorted_tables:
                if (await db.execute(select(1).select_from(table).limit(1))).scalar_one_or_none() is not None:
                    raise RuntimeError("Refusing to seed a non-empty database. Existing data was not changed.")
            password_hash = get_password_hash(password)
            university = University(name=f"[DEMO] {UNIVERSITY['name']}", domain=UNIVERSITY["domain"],
                province=UNIVERSITY["province"],
                campus_location=f"SRID=4326;POINT({UNIVERSITY['lng']} {UNIVERSITY['lat']})")
            db.add(university)
            await db.flush()
            landlords = []
            for index, item in enumerate(LANDLORDS, 1):
                user = User(email=f"demo.landlord.{index}@example.com", password_hash=password_hash,
                            role="landlord", is_active=True, email_verified_at=verified_at)
                db.add(user)
                await db.flush()
                landlord = Landlord(user_id=user.id, display_name=f"[DEMO] {item['name']}",
                                    verification_status="verified", verified_at=verified_at)
                db.add(landlord)
                await db.flush()
                landlords.append(landlord)
            students = []
            for index, item in enumerate(STUDENTS, 1):
                user = User(email=f"demo.student.{index}@example.com", password_hash=password_hash,
                            role="student", is_active=True, email_verified_at=verified_at)
                db.add(user)
                await db.flush()
                first, _, last = item["name"].partition(" ")
                student = Student(user_id=user.id, university_id=university.id,
                                  first_name=first, last_name=last or "Student",
                                  student_number=f"DEMO-{index:04d}", verification_tier=1)
                db.add(student)
                await db.flush()
                students.append(student)
            review_count = 0
            for item in ACCOMMODATIONS:
                accommodation = Accommodation(landlord_id=landlords[item["landlord_idx"]].id,
                    title=f"[DEMO] {item['title']}",
                    description="Synthetic demonstration listing. " + item["description"],
                    address=item["address"], location=f"SRID=4326;POINT({item['lng']} {item['lat']})",
                    price_min=item["price_min"], price_max=item["price_max"], status="approved")
                db.add(accommodation)
                await db.flush()
                selected = rng.sample(students, min(5, len(students)))
                mix = [("positive", rng.choice(REVIEW_TEMPLATES[0][1])) for _ in range(3)]
                mix += [("negative", rng.choice(REVIEW_TEMPLATES[1][1])),
                        ("neutral", rng.choice(REVIEW_TEMPLATES[2][1]))]
                rng.shuffle(mix)
                for student, (sentiment_hint, template) in zip(selected, mix):
                    rating = rng.choice([4, 5]) if sentiment_hint == "positive" else rng.choice([1, 2]) if sentiment_hint == "negative" else 3
                    db.add(Review(student_id=student.id, accommodation_id=accommodation.id,
                                  rating=rating, body=template.format(name=accommodation.title),
                                  status="pending_analysis"))
                    review_count += 1
            # One transaction: failure rolls back every demo insert.
    counts = {"landlords": len(landlords), "students": len(students),
              "accommodations": len(ACCOMMODATIONS), "pending_reviews": review_count}
    print("Demo seed complete: " + json.dumps(counts))
    print("Reviews remain pending for the normal Gemini analysis/moderation workflow. No AI or email calls were made.")
    return counts


def main():
    parser = argparse.ArgumentParser(description="Create synthetic data in an empty demo database only.")
    parser.add_argument("--demo", action="store_true", help="Explicitly confirm this is an empty demo database")
    args = parser.parse_args()
    try:
        asyncio.run(seed(demo=args.demo, password=os.getenv("DEMO_PASSWORD")))
    except RuntimeError as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
