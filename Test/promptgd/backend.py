from google import genai
from google.genai import types

from tenacity import retry, retry_if_exception_type, wait_fixed, stop_after_attempt
from dotenv import load_dotenv 
import os
import asyncio
import re
import polars as pl

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Explain how AI works in a few words",
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        temperature=0.2,
        max_output_tokens=1000,
    ),
)


class Parser:
    def __init__(self):
        pass    

class Utils:
    def __init__(self):
        pass

    @staticmethod
    def generate_prompts_pl(df: pl.DataFrame, template: str, new_col: str = "prompt") -> pl.DataFrame:
        """
        Generate prompts using a template with {placeholders}
        and Polars string expressions.
        """
        placeholders = re.findall(r"{(.*?)}", template)

        # Start building an expression
        expr = pl.lit(template)

        # For each placeholder, split and replace with column
        for ph in placeholders:
            before, after = expr, None

            # Split the template by this placeholder
            parts = template.split(f"{{{ph}}}")

            # Build expression using concat
            expr = pl.lit(parts[0])
            expr = expr + pl.col(ph).cast(pl.Utf8)  # insert column value

            # For the rest of the segments
            for p in parts[1:]:
                expr = expr + pl.lit(p)

            # Update template so next replacement is correct
            template = "".join(
                [parts[0]] + [f"{{{ph}}}{p}" for p in parts[1:]]
            )

        return df.with_columns(expr.alias(new_col))
        

class Generation:
    def __init__(
        self,
        api_key: str,
        model: str
    ):
        self.api_key = api_key
        self.client = genai.Client(api_key=self.api_key)
        self.model = model
    
    @retry(
        wait=wait_fixed(60),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
    )
    async def _generation_prompt(
        self,
        prompt: str,
        config: types.GenerateContentConfig = None
    ):
        response = await self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config
        )
        
        return response.text