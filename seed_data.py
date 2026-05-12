
import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.session import SessionLocal
from app.models.database import (
    GradeLevel,
    Subject,
    Department,
    School,
    User,
    UserRole,
    Grade,
    Learner,
    ParentLearner,
    Book,
    BookCopy,
    AIModelVersion,
)
from app.services.auth_service import _hash_password as hash_password


def seed():
    db = SessionLocal()
    try:
        if db.query(GradeLevel).first():
            print("Database already has data. Skipping seed.")
            return

        print("Seeding database...")

        grade_levels = []
        for name in ["Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5",
                     "Grade 6", "Grade 7", "Grade 8", "Grade 9", "Grade 10",
                     "Grade 11", "Grade 12"]:
            gl = GradeLevel(name=name)
            db.add(gl)
            grade_levels.append(gl)
        db.flush()
        print(f"  Created {len(grade_levels)} grade levels")

        # --- Subjects ---
        subjects = []
        for name in ["Mathematics", "English", "Science", "History",
                     "Geography", "Life Skills", "Technology", "Art",
                     "Physical Education", "Music"]:
            s = Subject(name=name)
            db.add(s)
            subjects.append(s)
        db.flush()
        print(f"  Created {len(subjects)} subjects")

        # --- Departments ---
        dept_gauteng = Department(name="Gauteng Department of Education")
        dept_wc = Department(name="Western Cape Department of Education")
        dept_kzn = Department(name="KwaZulu-Natal Department of Education")
        db.add_all([dept_gauteng, dept_wc, dept_kzn])
        db.flush()
        print("  Created 3 departments")

        # --- Schools ---
        schools_data = [
            {"department": dept_gauteng, "name": "Johannesburg Primary School", "city": "Johannesburg", "state": "Gauteng"},
            {"department": dept_gauteng, "name": "Pretoria High School", "city": "Pretoria", "state": "Gauteng"},
            {"department": dept_gauteng, "name": "Soweto Secondary School", "city": "Soweto", "state": "Gauteng"},
            {"department": dept_wc, "name": "Cape Town Academy", "city": "Cape Town", "state": "Western Cape"},
            {"department": dept_wc, "name": "Stellenbosch Primary", "city": "Stellenbosch", "state": "Western Cape"},
            {"department": dept_kzn, "name": "Durban Central School", "city": "Durban", "state": "KwaZulu-Natal"},
            {"department": dept_kzn, "name": "Pietermaritzburg High", "city": "Pietermaritzburg", "state": "KwaZulu-Natal"},
        ]
        schools = []
        for i, sd in enumerate(schools_data):
            school = School(
                department_id=sd["department"].id,
                name=sd["name"],
                address=f"{100 + i} Main Street",
                city=sd["city"],
                state=sd["state"],
                country="South Africa",
                latitude=-26.2 + i * 0.5,
                longitude=28.0 + i * 0.3,
                total_students=300 + i * 50,
                total_teachers=15 + i * 3,
            )
            db.add(school)
            schools.append(school)
        db.flush()
        print(f"  Created {len(schools)} schools")

        # --- Users ---
        users_data = [
            {"email": "admin@gauteng.edu.za", "name": "John Admin", "role": "DeptAdmin", "dept": dept_gauteng, "school": None},
            {"email": "admin@wc.edu.za", "name": "Sarah Admin", "role": "DeptAdmin", "dept": dept_wc, "school": None},
            {"email": "principal@jhb.edu.za", "name": "David Principal", "role": "SchoolAdmin", "dept": dept_gauteng, "school": schools[0]},
            {"email": "principal@pta.edu.za", "name": "Maria Principal", "role": "SchoolAdmin", "dept": dept_gauteng, "school": schools[1]},
            {"email": "principal@cpt.edu.za", "name": "Peter Principal", "role": "SchoolAdmin", "dept": dept_wc, "school": schools[3]},
            {"email": "teacher1@jhb.edu.za", "name": "Alice Teacher", "role": "Teacher", "dept": None, "school": schools[0]},
            {"email": "teacher2@jhb.edu.za", "name": "Bob Teacher", "role": "Teacher", "dept": None, "school": schools[0]},
            {"email": "teacher1@cpt.edu.za", "name": "Carol Teacher", "role": "Teacher", "dept": None, "school": schools[3]},
            {"email": "parent1@mail.com", "name": "James Parent", "role": "Parent", "dept": None, "school": None},
            {"email": "parent2@mail.com", "name": "Linda Parent", "role": "Parent", "dept": None, "school": None},
        ]
        users = []
        for ud in users_data:
            user = User(
                email=ud["email"],
                password_hash=hash_password("password123"),
                full_name=ud["name"],
                is_active=True,
                department_id=ud["dept"].id if ud["dept"] else None,
                school_id=ud["school"].id if ud["school"] else None,
            )
            db.add(user)
            users.append(user)
        db.flush()

        # Assign roles
        for user, ud in zip(users, users_data):
            role = UserRole(user_id=user.id, role=ud["role"])
            db.add(role)
        db.flush()
        print(f"  Created {len(users)} users with roles")

        # --- Grades (classes within schools) ---
        grades = []
        for school in schools[:4]:
            for gl in grade_levels[:5]:
                grade = Grade(school_id=school.id, name=f"{gl.name} - {school.name[:10]}")
                db.add(grade)
                grades.append(grade)
        db.flush()
        print(f"  Created {len(grades)} grades")

        # --- Learners ---
        learner_names = [
            ("Thabo", "Mokoena"), ("Naledi", "Dlamini"), ("Sipho", "Nkosi"),
            ("Lerato", "Molefe"), ("Kagiso", "Mthembu"), ("Zanele", "Khumalo"),
            ("Bongani", "Ndlovu"), ("Nomsa", "Zulu"), ("Themba", "Sithole"),
            ("Ayanda", "Mahlangu"), ("Mpho", "Maseko"), ("Lindiwe", "Ngcobo"),
            ("Tshepo", "Radebe"), ("Palesa", "Mkhize"), ("Siyabonga", "Cele"),
            ("Nompumelelo", "Shabalala"), ("Mandla", "Buthelezi"), ("Thandi", "Zwane"),
            ("Vusi", "Mabaso"), ("Nokuthula", "Dube"),
        ]
        learners = []
        for i, (first, last) in enumerate(learner_names):
            grade_idx = i % len(grades)
            learner = Learner(
                grade_id=grades[grade_idx].id,
                first_name=first,
                last_name=last,
            )
            db.add(learner)
            learners.append(learner)
        db.flush()
        print(f"  Created {len(learners)} learners")

        # --- Parent-Learner Links ---
        parent1 = users[8]  # James Parent
        parent2 = users[9]  # Linda Parent
        pl1 = ParentLearner(parent_id=parent1.id, learner_id=learners[0].id)
        pl2 = ParentLearner(parent_id=parent1.id, learner_id=learners[1].id)
        pl3 = ParentLearner(parent_id=parent2.id, learner_id=learners[2].id)
        pl4 = ParentLearner(parent_id=parent2.id, learner_id=learners[3].id)
        db.add_all([pl1, pl2, pl3, pl4])
        db.flush()
        print("  Created 4 parent-learner links")

        # --- Books ---
        books_data = [
            {"title": "Mathematics Grade 1", "subject": subjects[0], "grade": grade_levels[0], "isbn": "978-0-620-00001-1", "publisher": "Oxford SA", "author": "J. Smith"},
            {"title": "Mathematics Grade 2", "subject": subjects[0], "grade": grade_levels[1], "isbn": "978-0-620-00002-2", "publisher": "Oxford SA", "author": "J. Smith"},
            {"title": "Mathematics Grade 3", "subject": subjects[0], "grade": grade_levels[2], "isbn": "978-0-620-00003-3", "publisher": "Oxford SA", "author": "J. Smith"},
            {"title": "English Home Language Grade 1", "subject": subjects[1], "grade": grade_levels[0], "isbn": "978-0-620-00004-4", "publisher": "Pearson SA", "author": "M. Johnson"},
            {"title": "English Home Language Grade 2", "subject": subjects[1], "grade": grade_levels[1], "isbn": "978-0-620-00005-5", "publisher": "Pearson SA", "author": "M. Johnson"},
            {"title": "Natural Sciences Grade 4", "subject": subjects[2], "grade": grade_levels[3], "isbn": "978-0-620-00006-6", "publisher": "Via Afrika", "author": "P. Williams"},
            {"title": "Natural Sciences Grade 5", "subject": subjects[2], "grade": grade_levels[4], "isbn": "978-0-620-00007-7", "publisher": "Via Afrika", "author": "P. Williams"},
            {"title": "History Grade 6", "subject": subjects[3], "grade": grade_levels[5], "isbn": "978-0-620-00008-8", "publisher": "Maskew Miller", "author": "T. Brown"},
            {"title": "Geography Grade 7", "subject": subjects[4], "grade": grade_levels[6], "isbn": "978-0-620-00009-9", "publisher": "Maskew Miller", "author": "L. Davis"},
            {"title": "Life Skills Grade 3", "subject": subjects[5], "grade": grade_levels[2], "isbn": "978-0-620-00010-0", "publisher": "Shuter & Shooter", "author": "K. Wilson"},
        ]
        books = []
        for bd in books_data:
            book = Book(
                title=bd["title"],
                subject_id=bd["subject"].id,
                grade_level_id=bd["grade"].id,
                isbn=bd["isbn"],
                publisher=bd["publisher"],
                author=bd["author"],
                edition="1st",
            )
            db.add(book)
            books.append(book)
        db.flush()
        print(f"  Created {len(books)} books")

        # --- Book Copies (with QR codes) ---
        copies = []
        copy_num = 1
        for book in books[:5]:
            for school in schools[:3]:
                for i in range(3):
                    copy = BookCopy(
                        book_id=book.id,
                        school_id=school.id,
                        qr_code=f"QR-{copy_num:06d}",
                        condition="good",
                    )
                    db.add(copy)
                    copies.append(copy)
                    copy_num += 1
        db.flush()
        print(f"  Created {len(copies)} book copies")

        # --- AI Model Version ---
        ai_model = AIModelVersion(
            model_name="book-condition-scanner",
            model_version="1.0.0",
            model_type="book_condition",
            is_active=True,
        )
        db.add(ai_model)
        db.flush()
        print("  Created 1 AI model version (active)")

        db.commit()
        print("\n✅ Database seeded successfully!")
        print("\nLogin credentials (all passwords: password123):")
        print("  DeptAdmin:    admin@gauteng.edu.za")
        print("  DeptAdmin:    admin@wc.edu.za")
        print("  SchoolAdmin:  principal@jhb.edu.za")
        print("  SchoolAdmin:  principal@cpt.edu.za")
        print("  Teacher:      teacher1@jhb.edu.za")
        print("  Parent:       parent1@mail.com")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
