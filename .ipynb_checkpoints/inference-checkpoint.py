import os
import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer
from PIL import Image


# Define the model name and cache directory
model_name = "OpenGVLab/InternVL2-Llama3-76B"
cache_dir = "/model"

def fixed_get_imports(filename: str | os.PathLike) -> list[str]:
    """Work around for https://huggingface.co/microsoft/phi-1_5/discussions/72."""
    if not str(filename).endswith("/modeling_florence2.py"):
        return get_imports(filename)
    imports = get_imports(filename)
    imports.remove("flash_attn")
    return imports


with patch("transformers.dynamic_module_utils.get_imports", fixed_get_imports):

    # Download and load the model and tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, cache_dir=cache_dir)
    model = AutoModel.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
        cache_dir=cache_dir).eval()

generation_config = dict(max_new_tokens=1024, do_sample=False)

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

def build_transform(input_size):
    MEAN, STD = IMAGENET_MEAN, IMAGENET_STD
    transform = T.Compose([
        T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=MEAN, std=STD)
    ])
    return transform

def find_closest_aspect_ratio(aspect_ratio, target_ratios, width, height, image_size):
    best_ratio_diff = float('inf')
    best_ratio = (1, 1)
    area = width * height
    for ratio in target_ratios:
        target_aspect_ratio = ratio[0] / ratio[1]
        ratio_diff = abs(aspect_ratio - target_aspect_ratio)
        if ratio_diff < best_ratio_diff:
            best_ratio_diff = ratio_diff
            best_ratio = ratio
        elif ratio_diff == best_ratio_diff:
            if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                best_ratio = ratio
    return best_ratio

def dynamic_preprocess(image, min_num=1, max_num=12, image_size=448, use_thumbnail=False):
    orig_width, orig_height = image.size
    aspect_ratio = orig_width / orig_height

    # calculate the existing image aspect ratio
    target_ratios = set(
        (i, j) for n in range(min_num, max_num + 1) for i in range(1, n + 1) for j in range(1, n + 1) if
        i * j <= max_num and i * j >= min_num)
    target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

    # find the closest aspect ratio to the target
    target_aspect_ratio = find_closest_aspect_ratio(
        aspect_ratio, target_ratios, orig_width, orig_height, image_size)

    # calculate the target width and height
    target_width = image_size * target_aspect_ratio[0]
    target_height = image_size * target_aspect_ratio[1]
    blocks = target_aspect_ratio[0] * target_aspect_ratio[1]

    # resize the image
    resized_img = image.resize((target_width, target_height))
    processed_images = []
    for i in range(blocks):
        box = (
            (i % (target_width // image_size)) * image_size,
            (i // (target_width // image_size)) * image_size,
            ((i % (target_width // image_size)) + 1) * image_size,
            ((i // (target_width // image_size)) + 1) * image_size
        )
        # split the image
        split_img = resized_img.crop(box)
        processed_images.append(split_img)
    assert len(processed_images) == blocks
    if use_thumbnail and len(processed_images) != 1:
        thumbnail_img = image.resize((image_size, image_size))
        processed_images.append(thumbnail_img)
    return processed_images

def load_image(image_file, input_size=448, max_num=12):
    image = Image.open(image_file).convert('RGB')
    transform = build_transform(input_size=input_size)
    images = dynamic_preprocess(image, image_size=input_size, use_thumbnail=True, max_num=max_num)
    pixel_values = [transform(image) for image in images]
    pixel_values = torch.stack(pixel_values)
    return pixel_values

def process_image(image_path):
    """Process an image and return the model's output."""
    try:
        pixel_values = load_image(image_path, max_num=12).to(torch.bfloat16).cuda()

        question = '<image>\nYou are a helpful text extractor assistant. You are a preprocessing step for a larger AI agent pipeline. Your job is to pull form data and return it in a single paragraph in the format: Use the input title:  value. Each data sentence should be followed by a period. For context, your sentence is sent to a natural language parser which will extract data and enter it into a database. But do not worry about that, just read the image and return as much relevant information as possible. Sometimes, people filling out these forms will free write data on the form, so it does not have an explicit input title tied to it. However, the words are so niche the humans know what it means. In these instances, just return the words as you see them on the form and the later steps in the pipeline will know what to do. For example, sometimes people will write \"4 Max\" with \"4 Pro\" underneath in the top right hand corner of the form. All you need to do in these instances is return the explicit text. In this example: \"4 Max and 4 Pro\". You are just a cog in the machine, if you do your job well, then everybody else can do their job as well. But if you fail at your task, other people cannot do their job and you are going to waste time and resources. Remember -- only return a single paragraph!!! Nothing else!!!'
        response = model.chat(tokenizer, pixel_values, question, generation_config)
        return f'User: {question}\nAssistant: {response}'


        return f"Processed {os.path.basename(image_path)}"
    except Exception as e:
        return f"Error processing {os.path.basename(image_path)}: {str(e)}"

def process_images_in_directory(directory_path):
    """Process all images in a given directory."""
    results = []

    for filename in os.listdir(directory_path):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(directory_path, filename)
            result = process_image(image_path)
            results.append(result)
    return results

if __name__ == "__main__":
    # Update with your directory path
    directory_path = "test_images"
    results = process_images_in_directory(directory_path)
    for result in results:
        print(result)



