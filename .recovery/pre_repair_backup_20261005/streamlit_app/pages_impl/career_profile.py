"""Page: Career Profile."""
import streamlit as st
from src import user_data

def render():
    st.header("Career Profile")
    
    # Get existing profile
    profile = user_data.get_career_profile()
    
    with st.form("career_profile_form"):
        name = st.text_input("Name", value=profile["name"] if profile else "")
        location = st.text_input("Location", value=profile["location"] if profile else "")
        target_role = st.text_input("Target Role", value=profile["target_role"] if profile else "")
        target_location = st.text_input("Target Location", value=profile["target_location"] if profile else "")
        target_salary_min = st.number_input("Target Salary Min", value=float(profile["target_salary_min"]) if profile and profile["target_salary_min"] is not None else 0.0)
        target_salary_max = st.number_input("Target Salary Max", value=float(profile["target_salary_max"]) if profile and profile["target_salary_max"] is not None else 0.0)
        
        submitted = st.form_submit_button("Save Profile")
        if submitted:
            new_profile = {
                "name": name,
                "location": location,
                "target_role": target_role,
                "target_location": target_location,
                "target_salary_min": target_salary_min,
                "target_salary_max": target_salary_max
            }
            user_data.set_career_profile(new_profile)
            st.success("Profile saved successfully!")
    
    # Display current profile
    if profile:
        st.subheader("Current Profile")
        st.json(profile)
    else:
        st.info("No profile saved yet.")
