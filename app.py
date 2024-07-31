import os
import json
import tempfile

from flask import Flask, request, jsonify, send_from_directory
from loguru import logger
from flask_cors import CORS

from magic_pdf.pipe.UNIPipe import UNIPipe
from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter

import magic_pdf.model as model_config
model_config.__use_inside_model__ = True

app = Flask(__name__, static_folder='web')  # 设置静态文件目录
CORS(app)  # 启用CORS


@app.route('/pdf-extract', methods=['POST'])
def pdf_extract():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        try:
            # Save the file to a temporary location
            temp_dir = tempfile.TemporaryDirectory()
            pdf_path = os.path.join(temp_dir.name, file.filename)
            file.save(pdf_path)

            pdf_bytes = open(pdf_path, "rb").read()
            model_json = []  # Using internal model
            jso_useful_key = {"_pdf_type": "", "model_list": model_json}
            local_image_dir = os.path.join(temp_dir.name, 'images')
            image_writer = DiskReaderWriter(local_image_dir)
            pipe = UNIPipe(pdf_bytes, jso_useful_key, image_writer)

            # 根据pdf的元数据，判断是文本pdf，还是ocr pdf
            pipe.pipe_classify()

            if len(model_json) == 0:
                if model_config.__use_inside_model__:
                    pipe.pipe_analyze()
                else:
                    logger.error("need model list input")
                    return jsonify({'error': 'Model list input required'}), 500

            pipe.pipe_parse()
            md_content = pipe.pipe_mk_markdown(
                local_image_dir, drop_mode="none")
            temp_dir.cleanup()  # Clean up the temporary directory
            return jsonify({'markdown': md_content})

        except Exception as e:
            logger.exception(e)
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Unexpected error'}), 500


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
