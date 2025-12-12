import streamlit as st
import polars as pl
import pandas as pd

from backend import Utils

class Interface:
    def __init__(self):
        st.title("PromptGD Interface")
        st.write("Welcome to the PromptGD application!")
    
    def user_input(
            self,
            is_input_data: bool = True
    ):

        input_user_prompt = st.text_area(
            "Enter your prompt here:",
            height=300,
            help="Type or paste your prompt to get started.",
            placeholder="Type your Prompt here..."
        )
        input_user_objective = st.text_area(
            "Enter your objective here:",
            height=100,
            help="Type or paste your objective to guide the processing.",
            placeholder="Type your Objective here..."
        )

        col_1, col_2 = st.columns(2)
        with col_1:
            input_refinement_steps = st.number_input(
                label="Refinement Steps",
                value=2,
                min_value=2,
                max_value=5,
                step=1,
                help="Number of refinement steps to improve the output.",
            )
        with col_2:
            input_variant_prompt = st.number_input(
                label="Variant Prompt",
                value=2,
                min_value=2,
                max_value=3,
                step=1,
                help="Number of variant prompts to generate.",
            )
        
        return dict(
            user_prompt=input_user_prompt,
            user_objective=input_user_objective,
            refinement_steps=input_refinement_steps,
            variant_prompt=input_variant_prompt,
            is_input_data=is_input_data
        )   

    def sampel_data(self):
        input_csv_file = st.file_uploader(
            label="Upload CSV Sample Data File",
            type=["csv"],
            help="Upload a CSV file containing sample data for processing.",
        )
        if input_csv_file is not None:
            st.success("File uploaded successfully!")
            is_input_data = True
        else:
            is_input_data = False

        return input_csv_file, is_input_data

def main():

    if "dataframe" not in st.session_state:
        st.session_state["dataframe"] = None

    interface = Interface()
    utills = Utils()

    with st.expander("PromptGD", expanded=True ):
        csv_file, is_input_data = interface.sampel_data()
        user_inputs = interface.user_input(is_input_data=is_input_data)

        df = None
        if csv_file is not None:
            try:
                df = pl.read_csv(csv_file)
                st.session_state["dataframe"] = df
                df_head = df.head()
                st.dataframe(df_head)
            except Exception as e:
                st.error(f"Failed to read CSV: {e}")
        else:
            st.session_state["dataframe"] = None

    st.session_state["result_state"] = 0
    if st.button("Submit", type="primary", width="stretch"): 
        with st.expander("Submission Result", expanded=True ):
            if (not user_inputs.get("is_input_data", False)) or (user_inputs.get("user_prompt") == "" or user_inputs.get("user_objective") == ""):
                st.session_state["result_state"] = 0
                st.error("Please upload a CSV file or provide a prompt and objective before submitting.")
            else:
                st.session_state["result_state"] = 1
                if st.session_state["dataframe"] is not None:
                    new = utills.generate_prompts_pl(
                        df=st.session_state["dataframe"],
                        template=user_inputs.get("user_prompt"), 
                    )
                    st.dataframe(new)
                else:
                    st.warning("No CSV data available to process.")


    st.json(user_inputs)

if __name__ == "__main__":
    main()
