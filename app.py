from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import logging
import traceback

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)  # 添加日志

# 获取当前文件的绝对路径
basedir = os.path.abspath(os.path.dirname(__file__))
database_dir = os.path.join(basedir, 'database')
if not os.path.exists(database_dir):
    os.makedirs(database_dir)

database_path = os.path.join(database_dir, 'qianghua.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class UpgradeRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pattern_name = db.Column(db.String(50), nullable=False)
    operation_count = db.Column(db.Integer, nullable=False)
    broken_equipment = db.Column(db.String(100))
    target_level = db.Column(db.Integer, nullable=False)
    law_level = db.Column(db.Integer, default=0)
    success = db.Column(db.Boolean, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# 添加一个计算手数的函数
def calculate_operation_count(pattern_name, broken_equipment):
    # 计算路径层数
    path_count = len(pattern_name.split('-'))
    
    # 计算碎掉的装备数量
    broken_count = len(broken_equipment.split('+')) if broken_equipment else 0
    # 如果broken_equipment是空字符串，broken_count应该为0
    if not broken_equipment or broken_equipment.strip() == '':
        broken_count = 0
        
    return path_count + broken_count

# 添加一个格式化路径的函数
def format_pattern_name(pattern):
    # 移除所有空格
    pattern = pattern.strip().replace(' ', '')
    
    # 如果已经包含'-'，直接返回
    if '-' in pattern:
        return pattern
        
    # 将连续数字转换为带'-'的格式
    return '-'.join(list(pattern))

# 添加一个格式化碎掉装备记录的函数
def format_broken_equipment(broken):
    # 移除所有空格
    broken = broken.strip().replace(' ', '')
    
    # 如果已经包含'+'，直接返回
    if '+' in broken:
        return broken
        
    # 如果为空，返回空字符串
    if not broken:
        return ''
        
    # 将连续数字转换为带'+'的格式
    return '+'.join(list(broken))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/record', methods=['POST'])
def record_upgrade():
    try:
        if not request.is_json:
            app.logger.error("Request is not JSON")
            return jsonify({'status': 'error', 'message': 'Content-Type must be application/json'}), 400
        
        data = request.json
        app.logger.debug(f"Received data: {data}")
        
        # 验证法则等级和目标等级
        try:
            law_level = int(data.get('law_level', 0))
            target_level = int(data['target_level'])
        except (ValueError, TypeError) as e:
            app.logger.error(f"Error parsing numeric values: {e}")
            return jsonify({'status': 'error', 'message': '法则等级和目标等级必须是数字'}), 400

        # 验证法则等级范围
        if not (0 <= law_level <= 5):
            app.logger.error(f"Invalid law level value: {law_level}")
            return jsonify({'status': 'error', 'message': '法则等级必须在0-5之间'}), 400
            
        # 验证目标等级范围
        if not (7 <= target_level <= 10):
            app.logger.error(f"Invalid target level value: {target_level}")
            return jsonify({'status': 'error', 'message': '目标等级必须在7-10之间'}), 400

        # 格式化输入数据
        pattern_name = format_pattern_name(data['pattern_name'])
        broken_equipment = format_broken_equipment(data.get('broken_equipment', ''))
        
        try:
            # 创建新记录
            operation_count = calculate_operation_count(pattern_name, broken_equipment)
            record = UpgradeRecord(
                pattern_name=pattern_name,
                operation_count=operation_count,
                broken_equipment=broken_equipment,
                target_level=target_level,
                law_level=law_level,
                success=data['success']
            )
            db.session.add(record)
            db.session.commit()
            
            # 如果失败，返回下一个要碎的装备号码
            if not data['success']:
                next_broken = str(target_level - 1)
                new_broken = broken_equipment + '+' + next_broken if broken_equipment else next_broken
                return jsonify({
                    'status': 'success',
                    'next_broken_equipment': new_broken,
                    'continue_pattern': pattern_name
                })
            
            return jsonify({'status': 'success'})

        except Exception as e:
            db.session.rollback()
            error_trace = traceback.format_exc()
            app.logger.error(f"Database error: {str(e)}\nTraceback:\n{error_trace}")
            return jsonify({'status': 'error', 'message': f'数据库错误: {str(e)}'}), 500

    except Exception as e:
        error_trace = traceback.format_exc()
        app.logger.error(f"General error: {str(e)}\nTraceback:\n{error_trace}")
        return jsonify({'status': 'error', 'message': f'系统错误: {str(e)}'}), 500

@app.route('/analyze', methods=['GET'])
def analyze_patterns():
    # 获取查询参数
    target_level = request.args.get('target_level', type=int)
    law_level = request.args.get('law_level', type=int, default=0)
    pattern_name = request.args.get('pattern_name', '')
    broken_equipment = request.args.get('broken_equipment', '')

    # 构建基础查询
    query = UpgradeRecord.query.filter_by(law_level=law_level)
    
    # 添加目标等级筛选
    if target_level:
        query = query.filter_by(target_level=target_level)
        
    # 添加强化路径筛选
    if pattern_name:
        query = query.filter_by(pattern_name=pattern_name)
        
    # 添加碎掉装备记录筛选
    if broken_equipment:
        query = query.filter_by(broken_equipment=broken_equipment)

    # 获取所有记录
    records = query.all()
    
    # 按路径分组统计
    pattern_stats = {}
    for record in records:
        key = (record.pattern_name, record.broken_equipment)
        if key not in pattern_stats:
            pattern_stats[key] = {
                'pattern_name': record.pattern_name,
                'broken_equipment': record.broken_equipment,
                'success_count': 0,
                'failure_count': 0,
                'total_count': 0,
                'law_level': record.law_level,
                'target_level': record.target_level,
                'details': []
            }
        
        stats = pattern_stats[key]
        stats['total_count'] += 1
        if record.success:
            stats['success_count'] += 1
        else:
            stats['failure_count'] += 1
        
        stats['details'].append({
            'operation_count': record.operation_count,
            'broken_equipment': record.broken_equipment,
            'success': record.success,
            'timestamp': record.timestamp.isoformat()
        })
    
    # 计算成功率并转换为列表
    result = []
    for stats in pattern_stats.values():
        stats['success_rate'] = (stats['success_count'] / stats['total_count'] * 100) if stats['total_count'] > 0 else 0
        result.append({
            'pattern_name': stats['pattern_name'],
            'broken_equipment': stats['broken_equipment'],
            'success_rate': stats['success_rate'],
            'total_count': stats['total_count'],
            'success_count': stats['success_count'],
            'failure_count': stats['failure_count'],
            'law_level': stats['law_level'],
            'target_level': stats['target_level'],
            'details': stats['details']
        })
    
    # 按成功率降序排序并返回前10个
    result.sort(key=lambda x: (x['success_rate'], x['total_count']), reverse=True)
    return jsonify(result[:10])

@app.route('/stats', methods=['GET'])
def get_stats():
    try:
        law_level = request.args.get('law_level', type=int, default=0)
        app.logger.debug(f"Getting stats for law level: {law_level}")
        
        hand_stats = {7: {}, 8: {}, 9: {}, 10: {}}
        best_paths = {7: [], 8: [], 9: [], 10: {}}
        
        for target_level in [7, 8, 9, 10]:
            app.logger.debug(f"Processing target level: {target_level}")
            
            # 修改查询，直接从 UpgradeRecord 获取数据
            all_records = UpgradeRecord.query.filter_by(
                law_level=law_level,
                target_level=target_level
            ).all()
            
            # 获取成功记录
            success_records = [r for r in all_records if r.success]
            
            app.logger.debug(f"Found {len(success_records)} success records out of {len(all_records)} total records")
            
            # 统计手数
            hand_counts = {}
            for record in success_records:
                hand_counts[record.operation_count] = hand_counts.get(record.operation_count, 0) + 1
            
            # 按成功次数排序，取前4个最多的
            sorted_hands = sorted(hand_counts.items(), key=lambda x: x[1], reverse=True)[:4]
            total_success = len(success_records)
            
            hand_stats[target_level] = {
                'total_success': total_success,
                'top_hands': [
                    {
                        'hands': hands,
                        'count': count,
                        'percentage': (count/total_success*100) if total_success > 0 else 0
                    }
                    for hands, count in sorted_hands
                ] if success_records else []
            }
            
            # 按路径分组统计
            path_stats = {}
            for record in all_records:
                if record.pattern_name not in path_stats:
                    path_stats[record.pattern_name] = {
                        'success_count': 0,
                        'total_count': 0,
                        'pattern': record.pattern_name
                    }
                path_stats[record.pattern_name]['total_count'] += 1
                if record.success:
                    path_stats[record.pattern_name]['success_count'] += 1
            
            # 计算成功率
            for pattern_name in path_stats:
                total = path_stats[pattern_name]['total_count']
                success = path_stats[pattern_name]['success_count']
                path_stats[pattern_name]['success_rate'] = (success / total * 100) if total > 0 else 0
            
            # 按成功次数排序，取前三名
            sorted_paths = sorted(
                path_stats.values(),
                key=lambda x: x['success_count'],
                reverse=True
            )[:3]
            
            best_paths[target_level] = [
                {
                    'pattern': path['pattern'],
                    'successCount': path['success_count'],
                    'successRate': path['success_rate'],
                    'attempts': path['total_count']
                }
                for path in sorted_paths
            ]
        
        response_data = {
            'handStats': hand_stats,
            'bestPaths': best_paths
        }
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Error in get_stats: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# 添加一个清除数据的路由
@app.route('/clear_data', methods=['POST'])
def clear_data():
    try:
        # 只需要删除记录表
        UpgradeRecord.query.delete()
        db.session.commit()
        return jsonify({'status': 'success', 'message': '数据已清除'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 添加回退路由
@app.route('/rollback', methods=['POST'])
def rollback_last_record():
    try:
        # 获取最后一条记录
        last_record = UpgradeRecord.query.order_by(UpgradeRecord.id.desc()).first()
        if not last_record:
            return jsonify({'status': 'error', 'message': '没有可回退的记录'}), 400
        
        # 删除最后一条记录
        db.session.delete(last_record)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': '已回退最后一条记录',
            'record': {
                'pattern_name': last_record.pattern_name,
                'success': last_record.success,
                'law_level': last_record.law_level,
                'target_level': last_record.target_level
            }
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in rollback: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/debug_patterns', methods=['GET'])
def debug_patterns():
    try:
        # 从 UpgradeRecord 获取统计数据
        records = UpgradeRecord.query.all()
        pattern_stats = {}
        
        for record in records:
            key = (record.pattern_name, record.law_level, record.target_level)
            if key not in pattern_stats:
                pattern_stats[key] = {
                    'pattern_name': record.pattern_name,
                    'law_level': record.law_level,
                    'target_level': record.target_level,
                    'attempts': 0,
                    'successes': 0,
                    'failures': 0
                }
            
            stats = pattern_stats[key]
            stats['attempts'] += 1
            if record.success:
                stats['successes'] += 1
            else:
                stats['failures'] += 1
        
        return jsonify(list(pattern_stats.values()))
    except Exception as e:
        app.logger.error(f"Error in debug_patterns: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/debug_records', methods=['GET'])
def debug_records():
    try:
        records = UpgradeRecord.query.all()
        records_data = []
        for r in records:
            records_data.append({
                'pattern_name': r.pattern_name,
                'operation_count': r.operation_count,
                'broken_equipment': r.broken_equipment,
                'target_level': r.target_level,
                'success': r.success,
                'timestamp': r.timestamp.isoformat()
            })
        return jsonify(records_data)
    except Exception as e:
        app.logger.error(f"Error in debug_records: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/reset_database', methods=['POST'])
def reset_database():
    try:
        # 删除所有表
        db.drop_all()
        # 重新创建所有表
        db.create_all()
        return jsonify({'status': 'success', 'message': '数据库已重置'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001) 