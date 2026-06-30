"""Curated high-value tech/ops skill synonyms for the Toronto market.

flashtext matches whole tokens, so common acronyms and multi-word tools that
appear in job titles are added explicitly. Maps synonym -> canonical skill name.
The transform resolves canonical names to Lightcast IDs where possible, else
mints a stable local id (``LOCAL:<name>``).
"""

CURATED_SKILLS = {
    # languages
    "python": "Python", "sql": "SQL", "java": "Java", "javascript": "JavaScript",
    "typescript": "TypeScript", "c++": "C++", "c#": "C#", "go": "Go (Programming Language)",
    "rust": "Rust", "scala": "Scala", "r": "R (Programming Language)", "php": "PHP",
    # data / cloud
    "aws": "Amazon Web Services", "azure": "Microsoft Azure", "gcp": "Google Cloud Platform",
    "docker": "Docker", "kubernetes": "Kubernetes", "terraform": "Terraform",
    "spark": "Apache Spark", "hadoop": "Hadoop", "kafka": "Apache Kafka",
    "snowflake": "Snowflake", "databricks": "Databricks", "airflow": "Apache Airflow",
    "ci/cd": "CI/CD", "etl": "Extract Transform Load (ETL)",
    # bi / analytics
    "power bi": "Power BI", "powerbi": "Power BI", "tableau": "Tableau",
    "excel": "Microsoft Excel", "looker": "Looker", "sas": "SAS (Software)",
    # web / frameworks
    "react": "React (Web Framework)", "angular": "Angular", "vue": "Vue.js",
    "node.js": "Node.js", "nodejs": "Node.js", "django": "Django", "flask": "Flask",
    ".net": ".NET Framework", "spring": "Spring Framework",
    # ops / pm / crm
    "salesforce": "Salesforce", "hubspot": "HubSpot", "jira": "Atlassian JIRA",
    "confluence": "Confluence", "sap": "SAP", "workday": "Workday",
    "agile": "Agile Methodology", "scrum": "Scrum (Software Development)",
    "kanban": "Kanban", "lean": "Lean Manufacturing",
    # ai
    "machine learning": "Machine Learning", "deep learning": "Deep Learning",
    "nlp": "Natural Language Processing", "prompt engineering": "Prompt Engineering",
    "llm": "Large Language Models", "generative ai": "Generative Artificial Intelligence",
    "pytorch": "PyTorch", "tensorflow": "TensorFlow",
    # certs
    "pmp": "Project Management Professional (PMP)", "cpa": "Certified Public Accountant",
    "cfa": "Chartered Financial Analyst", "six sigma": "Six Sigma",
}
