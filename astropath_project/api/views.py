from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import CustomerDetailsSerializer
from .serializers import CustomerDetailsLimitedSerializer
from .models import CustomerDetails
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from .navatara_table import NavataraCalculator
from .transit_table import TransitCalculator
from .astrological_subject import AstrologicalSubject
from .report import Report 
from .dasha_calculator import DashaCalculator
from kerykeion import Report as BaseReport
import requests
import pytz
from datetime import datetime
from django.conf import settings
import time
from requests.exceptions import RequestException

#-----------------------------------------------------Customer Birth Details------------------------------------------------------

class CustomerDetailsAPIView(APIView):
    def post(self, request):
        serializer = CustomerDetailsSerializer(data=request.data)
        if serializer.is_valid():
            try:
                existing_record = CustomerDetails.objects.filter(
                    mobile_no = serializer.validated_data['mobile_no'],
                    # birth_date=serializer.validated_data['birth_date']
                ).first()

                if existing_record:
                    latitude, longitude = self.get_lat_long(serializer.validated_data['birth_place'])
                    if latitude is not None and longitude is not None:
                        existing_record.birth_time = serializer.validated_data['birth_time']
                        existing_record.birth_place = serializer.validated_data['birth_place']
                        existing_record.latitude = self.round_decimal(latitude)
                        existing_record.longitude = self.round_decimal(longitude)
                        existing_record.save()
                        return Response(CustomerDetailsSerializer(existing_record).data, status=status.HTTP_200_OK)
                    else:
                        return Response({"error": "Unable to geocode the birth place"}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    latitude, longitude = self.get_lat_long(serializer.validated_data['birth_place'])
                    if latitude is not None and longitude is not None:
                        customer = serializer.save(
                            latitude=self.round_decimal(latitude),
                            longitude=self.round_decimal(longitude)
                        )
                        return Response(CustomerDetailsSerializer(customer).data, status=status.HTTP_201_CREATED)
                    else:
                        return Response({"error": "Unable to geocode the birth place"}, status=status.HTTP_400_BAD_REQUEST)
            except ValidationError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def get_lat_long(self, place):
        geolocator = Nominatim(user_agent="astrology_app")
        max_attempts = 3
        attempts = 0
        
        while attempts < max_attempts:
            try:
                location = geolocator.geocode(place)
                if location:
                    return location.latitude, location.longitude
                else:
                    return None, None
            except (GeocoderTimedOut, GeocoderUnavailable):
                attempts += 1
        
        return None, None

    def round_decimal(self, value):
        return Decimal(value).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    

#-------------------------------------------Fetch Customer Details Using Customer_id---------------------------------------------------

class CustomerDetailsGetAPIView(APIView):
    def get(self, request, customer_id):
        try:
            customer = CustomerDetails.objects.get(id=customer_id)
            serializer = CustomerDetailsLimitedSerializer(customer)
            
            if not serializer.data:
                return Response({
                    "error": "Serializer produced empty data",
                    "customer_fields": [field.name for field in CustomerDetails._meta.fields],
                    "serializer_fields": serializer.fields.keys()
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        except CustomerDetails.DoesNotExist:
            return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"error": "Invalid Customer ID"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "error": str(e),
                "type": str(type(e))
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#----------------------------------------------------Navatara Data---------------------------------------------------------------------
        
class NavataraAPIView(APIView):
    def post(self, request):
        try:
            customer_id = request.data.get('id')
            if not customer_id:
                return Response({"error": "Customer ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            calculator = NavataraCalculator(customer_id)
            result = calculator.calculate()
            return Response(result, status=status.HTTP_200_OK)
        except CustomerDetails.DoesNotExist:
            return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#-----------------------------------------------------Transit Data--------------------------------------------------------------------

class TransitAPIView(APIView):
    def post(self, request):
        try:
            customer_id = request.data.get('id')
            if not customer_id:
                return Response({"error": "Customer ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            calculator = TransitCalculator(customer_id)
            result = calculator.calculate()
            return Response(result, status=status.HTTP_200_OK)
        except CustomerDetails.DoesNotExist:
            return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
#-------------------------------------------------------Planets & Apects Data--------------------------------------------------------------------

class PlanetsAPIView(APIView):
    def post(self, request):
        try:
            customer_id = request.data.get('id')
            if not customer_id:
                return Response({"error": "Customer ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            customer_details = CustomerDetails.objects.get(id=customer_id)
            
            birth_date = customer_details.birth_date
            birth_time = customer_details.birth_time
            birth_place = customer_details.birth_place
            
            year, month, day = birth_date.year, birth_date.month, birth_date.day
            hour, minute = birth_time.hour, birth_time.minute
            
            place_parts = birth_place.split(',')
            city = place_parts[0].strip()
            country = place_parts[-1].strip() if len(place_parts) > 1 else ""
            
            subject = AstrologicalSubject(
                name=customer_details.name,
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                city=city,
                nation=country,
                lng=customer_details.longitude,
                lat=customer_details.latitude,
                tz_str="Asia/Kolkata",
                zodiac_type="Sidereal",
                sidereal_mode="LAHIRI",
                houses_system_identifier='W',
                online=False
            )
            
            report = Report(subject)
            
            planets_data = report.get_planets_with_aspects()
           
            response_data = {
                "ascendant": {
                    "sign": subject.ascendant_sign,
                    "position": round(subject.ascendant_degree, 2)
                },
                "planets": planets_data
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except CustomerDetails.DoesNotExist:
            return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#----------------------------------------------------Dasha Calculator-------------------------------------------------------------------

class DashaAPIView(APIView):
    def post(self, request):
        try:
            customer_id = request.data.get('id')
            if not customer_id:
                return Response({"error": "Customer ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            calculator = DashaCalculator(customer_id)
            result = calculator.calculate()
            return Response(result, status=status.HTTP_200_OK)
        except CustomerDetails.DoesNotExist:
            return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
#----------------------------------------------Good Bad Times--------------------------------------------------------------------------

class GoodBadTimesAPIView(APIView):
    def get(self, request):
        LATITUDE = 28.6279
        LONGITUDE = 77.3749
        TIMEZONE = 5.5

        # API_KEY = "3Jl00g95af4w4ZDw53Uzy215P8LuRnmCa0jEuDOT"
        API_KEY = settings.APIASTRO_API_KEY

        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist)

        payload = {
            "year": current_time.year,
            "month": current_time.month,
            "date": current_time.day,
            "hours": current_time.hour,
            "minutes": current_time.minute,
            "seconds": current_time.second,
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "timezone": TIMEZONE,
            "config": {
                "observation_point": "geocentric",
                "ayanamsha": "lahiri"
            }
        }

        headers = {
            "x-api-key": API_KEY,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post('https://json.apiastro.com/good-bad-times', json=payload, headers=headers)
            response.raise_for_status() 

            return Response(response.json(), status=status.HTTP_200_OK)

        except requests.RequestException as e:
            return Response({"error": f"API request failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#----------------------------------------------Divisional Charts----------------------------------------------------------------------

# class DivisionalChartsAPIView(APIView):
#     def get(self, request, customer_id):
#         try:
#             customer = CustomerDetails.objects.get(id=customer_id)
#         except CustomerDetails.DoesNotExist:
#             return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

#         payload = {
#             "year": customer.birth_date.year,
#             "month": customer.birth_date.month,
#             "date": customer.birth_date.day,
#             "hours": customer.birth_time.hour,
#             "minutes": customer.birth_time.minute,
#             "seconds": customer.birth_time.second,
#             "latitude": float(customer.latitude),
#             "longitude": float(customer.longitude),
#             "timezone": 5.5,
#             "settings": {
#                 "observation_point": "topocentric",
#                 "ayanamsha": "lahiri"
#             }
#         }

#         API_KEY = settings.APIASTRO_API_KEY
#         headers = {
#             "x-api-key": API_KEY,
#             "Content-Type": "application/json"
#         }

#         chart_urls = [
#            "https://json.apiastro.com/d2-chart-info",
#             # "https://json.apiastro.com/d3-chart-info",
#             # "https://json.apiastro.com/d4-chart-info",
#             # "https://json.apiastro.com/d5-chart-info",
#             # "https://json.apiastro.com/d6-chart-info",
#             # "https://json.apiastro.com/d7-chart-info",
#             # "https://json.apiastro.com/d8-chart-info",
#             # "https://json.apiastro.com/navamsa-chart-info",
#             # "https://json.apiastro.com/d10-chart-info",
#             # "https://json.apiastro.com/d11-chart-info",
#             # "https://json.apiastro.com/d12-chart-info",
#             # "https://json.apiastro.com/d16-chart-info",
#             # "https://json.apiastro.com/d20-chart-info",
#             # "https://json.apiastro.com/d24-chart-info",
#             # "https://json.apiastro.com/d27-chart-info",
#             # "https://json.apiastro.com/d30-chart-info",
#             # "https://json.apiastro.com/d40-chart-info",
#             # "https://json.apiastro.com/d45-chart-info",
#             # "https://json.apiastro.com/d60-chart-info",
#         ]

#         results = {}

#         def make_request_with_retry(url, max_retries=3, delay=0.5):
#             for attempt in range(max_retries):
#                 try:
#                     response = requests.post(url, json=payload, headers=headers)
#                     response.raise_for_status()
#                     return response.json()
#                 except RequestException as e:
#                     if response.status_code == 429 and attempt < max_retries - 1:
#                         time.sleep(delay * (2 ** attempt))  # Exponential backoff
#                     else:
#                         return {"error": f"API request failed: {str(e)}"}
#             return {"error": "Max retries reached"}

#         for url in chart_urls:
#             chart_name = url.split('/')[-1].split('-')[0].upper()
#             results[chart_name] = make_request_with_retry(url)
#             time.sleep(0.5)  # Add a 1-second delay between requests

#         return Response(results, status=status.HTTP_200_OK)

class BaseChartAPIView(APIView):
    """Base class for all chart API views"""
    
    def get_chart_data(self, customer, chart_url):
        payload = {
            "year": customer.birth_date.year,
            "month": customer.birth_date.month,
            "date": customer.birth_date.day,
            "hours": customer.birth_time.hour,
            "minutes": customer.birth_time.minute,
            "seconds": customer.birth_time.second,
            "latitude": float(customer.latitude),
            "longitude": float(customer.longitude),
            "timezone": 5.5,
            "settings": {
                "observation_point": "topocentric",
                "ayanamsha": "lahiri"
            }
        }

        headers = {
            "x-api-key": settings.APIASTRO_API_KEY,
            "Content-Type": "application/json"
        }

        def make_request_with_retry(max_retries=3, delay=0.5):
            for attempt in range(max_retries):
                try:
                    response = requests.post(chart_url, json=payload, headers=headers)
                    response.raise_for_status()
                    return response.json()
                except RequestException as e:
                    if response.status_code == 429 and attempt < max_retries - 1:
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff
                    else:
                        return {"error": f"API request failed: {str(e)}"}
            return {"error": "Max retries reached"}

        return make_request_with_retry()

    def get(self, request, customer_id):
        try:
            customer = CustomerDetails.objects.get(id=customer_id)
        except CustomerDetails.DoesNotExist:
            return Response(
                {"error": "Customer not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        chart_data = self.get_chart_data(customer, self.chart_url)
        return Response(chart_data, status=status.HTTP_200_OK)
    
class D2ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d2-chart-info"

class D3ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d3-chart-info"

class D4ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d4-chart-info"

class D7ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d7-chart-info"

class NavamsaChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/navamsa-chart-info"

class D10ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d10-chart-info"

class D12ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d12-chart-info"

class D16ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d16-chart-info"

class D20ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d20-chart-info"

class D24ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d24-chart-info"

class D27ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d27-chart-info"

class D30ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d30-chart-info"

class D40ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d40-chart-info"

class D45ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d45-chart-info"

class D60ChartAPIView(BaseChartAPIView):
    chart_url = "https://json.apiastro.com/d60-chart-info"

