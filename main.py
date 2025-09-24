# !/usr/bin/python3
# -*- coding: utf-8 -*-
"""
@File  : main.py
@Author: White Gui
@Date  : 2025/9/24
@Desc :
"""
# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import string as st
from dateutil import parser
import matplotlib.image as mpimg
import cv2
from passporteye import read_mrz
import json
import easyocr
import warnings

# 忽略警告
warnings.filterwarnings('ignore')

# -------------------------- 初始化配置 --------------------------
# 加载OCR引擎（EasyOCR，英文）
reader = easyocr.Reader(lang_list=['en'], gpu=False)  # 如有GPU可设为True加速

# 加载国家代码映射（需提前准备country_codes.json）
with open('country_codes.json') as f:
    country_codes = json.load(f)


# -------------------------- 工具函数 --------------------------
def parse_date(date_str, iob=True):
    """将字符串日期转为DD/MM/YYYY格式"""
    try:
        date_obj = parser.parse(date_str, yearfirst=True).date()
        return date_obj.strftime('%d/%m/%Y')
    except Exception as e:
        print(f"日期解析失败: {date_str}, 错误: {e}")
        return date_str


def clean(text):
    """清理字符串：保留字母数字，转大写"""
    return ''.join(i for i in text if i.isalnum()).upper()


def get_country_name(country_code):
    """根据ISO 3166-1 alpha-3代码获取国家名称"""
    for country in country_codes:
        if country.get('alpha-3') == country_code:
            return country.get('name', '').upper()
    return country_code  # 未找到时返回原代码


def get_sex(code):
    """将护照性别代码转为M/F"""
    code = code.upper()
    if code in ['M', 'F']:
        return code
    elif code == '0':
        return 'M'
    else:
        return 'F'


def print_data(data):
    """格式化打印提取的信息"""
    for key in data.keys():
        info = key.replace('_', ' ').capitalize()
        print(f"{info}\t:\t{data[key]}")
    return


# -------------------------- 核心功能：护照信息提取 --------------------------
def get_passport_data(img_path_or_name):
    """
    从护照图像中提取个人信息
    Args:
        img_path_or_name (str): 护照图像路径 或 images目录下的文件名（如"passport_temgoua.png"）
    Returns:
        dict: 包含姓名、性别、出生日期等信息的字典
    """
    user_info = {}
    # 处理路径：如果是文件名则拼接images目录
    if not os.path.exists(img_path_or_name):
        img_path = os.path.join('./images/', img_path_or_name)
    else:
        img_path = img_path_or_name

    # 1. 提取MRZ区域（Machine Readable Zone）
    try:
        mrz = read_mrz(img_path, save_roi=True)
    except Exception as e:
        print(f"无法读取MRZ区域: {img_path}, 错误: {e}")
        return None

    if not mrz:
        print(f"机器无法识别MRZ区域: {img_path}")
        return None

    # 2. 保存并预处理MRZ ROI图像
    roi_save_path = 'tmp_mrz_roi.png'
    mpimg.imsave(roi_save_path, mrz.aux['roi'], cmap='gray')

    # 3. 使用EasyOCR识别MRZ文本
    try:
        img = cv2.imread(roi_save_path)
        img = cv2.resize(img, (1110, 140))  # 调整到MRZ标准尺寸
        allowlist = st.ascii_letters + st.digits + '< '  # 允许的字符集
        mrz_text = reader.readtext(img, paragraph=False, detail=0, allowlist=allowlist)
    except Exception as e:
        print(f"OCR识别失败: {roi_save_path}, 错误: {e}")
        os.remove(roi_save_path)
        return None

    print(f"success to read image, get passport text: {mrz_text}")
    # 4. 解析MRZ文本（分为两行：Line A和Line B）
    if len(mrz_text) < 2:
        print("MRZ文本行数不足")
        os.remove(roi_save_path)
        return None

    line_a, line_b = mrz_text[0].upper(), mrz_text[1].upper()

    # 补全长度至44字符（MRZ标准长度）
    line_a = line_a.ljust(44, '<')
    line_b = line_b.ljust(44, '<')

    # 5. 提取并清洗信息
    try:
        # 姓名（Line A的第5-44位，用<<分割姓和名）
        surname_names = line_a[5:44].split('<<', 1)
        surname = surname_names[0].replace('<', ' ').strip()
        name = surname_names[1].replace('<', ' ').strip() if len(surname_names) > 1 else ''

        # 性别（Line B的第20位）
        sex_code = clean(line_b[20])
        sex = get_sex(sex_code)

        # 出生日期（Line B的第13-19位：YYMMDD）
        dob_str = clean(line_b[13:19])
        date_of_birth = parse_date(dob_str)

        # 国籍（Line B的第10-13位：ISO 3166-1 alpha-3）
        nationality_code = clean(line_b[10:13])
        nationality = get_country_name(nationality_code)

        # 护照类型（Line A的第0-2位）
        passport_type = clean(line_a[0:2])

        # 护照号码（Line B的第0-9位）
        passport_number = clean(line_b[0:9])

        # 签发国（Line A的第2-5位：ISO 3166-1 alpha-3）
        issuing_country_code = clean(line_a[2:5])
        issuing_country = get_country_name(issuing_country_code)

        # 有效期（Line B的第21-27位：YYMMDD）
        exp_date_str = clean(line_b[21:27])
        expiration_date = parse_date(exp_date_str)

        # 个人号码（Line B的第28-42位）
        personal_number = clean(line_b[28:42])

    except Exception as e:
        print(f"信息解析失败: {e}")
        os.remove(roi_save_path)
        return None

    # 组装结果
    user_info = {
        "surname": surname,
        "name": name,
        "sex": sex,
        "date_of_birth": date_of_birth,
        "nationality": nationality,
        "passport_type": passport_type,
        "issuing_country": issuing_country,
        "passport_number": passport_number,
        "expiration_date": expiration_date,
        "personal_number": personal_number
    }

    # 清理临时文件
    os.remove(roi_save_path)
    return user_info


# -------------------------- 示例调用 --------------------------
if __name__ == "__main__":
    # 测试用例（需确保images目录下有对应图片）
    test_images = ["passport_temgoua.png", "passport_1.png","img-long.png"]

    for img_name in test_images:
        print(f"== == = 处理图片: {img_name} == == = ")
        data = get_passport_data(img_name)
        if data:
            print_data(data)