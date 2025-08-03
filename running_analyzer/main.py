from transformers import AutoModelForCausalLM, AutoTokenizer

def main():

    model_name = "Qwen/Qwen3-0.6B"

    # load the tokenizer and the model
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype="auto",
        device_map="auto"
    )

    # prepare the model input
    prompt = """
    You are a running coach. Based on the runner's input (avg heart rate, pace, cadence, and weekly mileage), create a 7-day running plan.
For each day, include: run type, distance or time, pace range or heart rate zone, and purpose.
Keep the plan balanced for a moderately fit runner aiming to improve endurance and efficiency.

Input: "Avg HR: 152 bpm, Pace: 5:10 min/km, Cadence: 168 spm, Weekly mileage: 35 km.
"""
    messages = [
        {"role": "user", "content": prompt}
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=True # Switches between thinking and non-thinking modes. Default is True.
    )
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    # conduct text completion
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=32768
    )
    output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist() 

    # parsing thinking content
    try:
        # rindex finding 151668 (</think>)
        index = len(output_ids) - output_ids[::-1].index(151668)
    except ValueError:
        index = 0

    thinking_content = tokenizer.decode(output_ids[:index], skip_special_tokens=True).strip("\n")
    content = tokenizer.decode(output_ids[index:], skip_special_tokens=True).strip("\n")

    print("thinking content:", thinking_content)
    print("content:", content)

if __name__ == "__main__":
    main()
