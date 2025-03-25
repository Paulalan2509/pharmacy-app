from django.shortcuts import render, redirect, get_object_or_404
from .models import Product, Category, Profile, ProductReview
from django.contrib.auth import authenticate, login, logout, admin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import SignUpForm, UpdateUserForm, ChangePasswordForm, UserInfoForm, ProductReviewForm
from django.db.models import Q
import json
from cart.cart import Cart
from payment.forms import ShippingForm
from django.core.paginator import Paginator
from payment.models import ShippingAddress, Order, OrderItem


def home(request):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None

    return render(request, 'index.html', {'user_profile': user_profile})


def contact(request):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None
    return render(request, 'contact.html', {'user_profile': user_profile})


def faq(request):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None
    return render(request, 'faq.html', {'user_profile': user_profile})


def store(request):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None
    # Start with all products
    products = Product.objects.all()

    # Get all categories for the filter sidebar
    categories = Category.objects.all()

    # Sort products
    sort = request.GET.get('sort')
    if sort:
        if sort == 'price_asc':
            products = products.order_by('price')
        elif sort == 'price_desc':
            products = products.order_by('-price')
        elif sort == 'name_asc':
            products = products.order_by('name')
        elif sort == 'name_desc':
            products = products.order_by('-name')

    # Filter by price range
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # Filter by sale items
    if request.GET.get('on_sale'):
        products = products.filter(is_sale=True)

    # Filter by categories
    category_ids = request.GET.getlist('category')
    if category_ids:
        products = products.filter(category__id__in=category_ids)

        # Pagination
    paginator = Paginator(Product.objects.all(), 6)  # Show  6 products per page
    page_number = request.GET.get('page', 1)
    page_objects = paginator.get_page(page_number)

    return render(request, 'pharmacy.html', {'products': products, "categories": categories, 'page_obj': page_objects, 'user_profile': user_profile})



def dashboard(request):
    if request.user.is_authenticated and request.user.is_superuser:
        profiles = Profile.objects.all()
        not_shipped_orders = Order.objects.filter(shipped=False)
        shipped_orders = Order.objects.filter(shipped=True)

        context = {
            'profiles': profiles,
            'not_shipped_orders': not_shipped_orders,
            'shipped_orders': shipped_orders,
        }

        return render(request, 'dashboard.html', context)
    else:
        messages.success(request, "Access Denied")
        return redirect('home')

def about(request):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None
    return render(request, 'about.html', {'user_profile': user_profile})


def login_user(request):
    error_message = None

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        remember_me = request.POST.get('remember', None)

        # Form validation
        if not username:
            error_message = "Username is required."
            return render(request, 'login.html', {'error_message': error_message})

        if not password:
            error_message = "Password is required."
            return render(request, 'login.html', {'error_message': error_message})

        # Authenticate user
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Set session expiry based on remember me checkbox
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
                request.session.modified = True
            else:
                request.session.set_expiry(0)  # Browser close

            # Do some shopping cart stuff
            try:
                current_user = Profile.objects.get(user__id=request.user.id)
                # Get their saved cart from database
                saved_cart = current_user.old_cart
                # Convert database string to python dictionary
                if saved_cart:
                    # Convert to dictionary using JSON
                    converted_cart = json.loads(saved_cart)
                    # Add the loaded cart dictionary to our session
                    # Get the cart
                    cart = Cart(request)
                    # Loop through the cart and add the items from the database
                    for key, value in converted_cart.items():
                        cart.db_add(product=key, quantity=value)
            except Exception as e:
                print(f"Error loading cart: {e}")

            messages.success(request, 'You Have Been Logged in successfully')
            return redirect('pharmacy')
        else:
            error_message = "Invalid username or password. Please try again."
            return render(request, 'login.html', {'error_message': error_message})
    else:
        return render(request, 'login.html', {})


def logout_user(request):
    logout(request)
    messages.info(request, 'You have been logged out... Thanks for stopping by...')
    return redirect('home')


def register_user(request):
    form = SignUpForm()
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            # log in user
            user = authenticate(username=username, password=password)
            login(request, user)
            messages.info(request, 'Username Created - Please Fill Out Your User Info Below.......')
            return redirect('update_info')
        else:
            messages.warning(request, 'Whoops! there was problem registering you please try again')
            return redirect('register')
    else:
        return render(request, 'register.html', {'form': form})


def product(request, pk):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None

    product = get_object_or_404(Product, id=pk)
    reviews = product.reviews.all().order_by('-date')
    average_rating = product.average_rating()

    if request.method == 'POST' and request.user.is_authenticated:
        form = ProductReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
            return redirect('product', pk=pk)
    else:
        form = ProductReviewForm()

    context = {
        'product': product,
        'reviews': reviews,
        'average_rating': average_rating,
        'form': form,
    }
    return render(request, 'product.html', context)


@login_required
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        form = ProductReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
            return redirect('product', pk=product_id)
    else:
        form = ProductReviewForm()
    return render(request, 'product.html', {'form': form, 'product': product, 'user_profile': user_profile})


def category(request, foo):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None

    # replace hyphens with spaces
    foo = foo.replace('-', ' ')
    # Grab the category from the url
    try:
        # look up the category
        category = Category.objects.get(name=foo)

        # Get all products in that category
        products = Product.objects.filter(category=category)
        return render(request, 'category.html', {'products': products, 'category': category, 'user_profile': user_profile})

    except:
        messages.error(request, 'That Category Doesnt Exist....')
        return redirect('home')


def category_summary(request):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None

    categories = Category.objects.all()
    return render(request, 'category_summary.html', {"categories": categories, 'user_profile': user_profile})


def update_user(request):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None

    if request.user.is_authenticated:
        current_user = User.objects.get(id=request.user.id)
        user_form = UpdateUserForm(request.POST or None, instance=current_user)

        if user_form.is_valid():
            user_form.save()

            login(request, current_user)
            messages.success(request, "User Has Been Updated!!")
            return redirect('home')
        return render(request, "update_user.html", {'user_form': user_form, 'user_profile': user_profile}, )
    else:
        messages.warning(request, "You Must Be Logged In To Access That Page!!")
        return redirect('home')


def update_password(request):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None

    if request.user.is_authenticated:
        current_user = request.user
        # Did they fill out the form
        if request.method == 'POST':
            form = ChangePasswordForm(current_user, request.POST)
            # Is the form valid
            if form.is_valid():
                form.save()
                messages.success(request, "Your Password Has Been Updated...")
                login(request, current_user)
                return redirect('update_user')
            else:
                for error in list(form.errors.values()):
                    messages.error(request, error)
                return redirect('update_password')
        else:
            form = ChangePasswordForm(current_user)
            return render(request, "update_password.html", {'form': form, 'user_profile': user_profile})
    else:
        messages.warning(request, "You Must Be Logged In To View That Page...")
        return redirect('home')


def update_info(request):
    # Redirect if not authenticated
    if not request.user.is_authenticated:
        messages.warning(request, "You Must Be Logged In To Access That Page!!")
        return redirect('home')

    # Get user profile
    user_profile = Profile.objects.get(user=request.user)
    current_user = Profile.objects.get(user__id=request.user.id)
    shipping_user = ShippingAddress.objects.get(user__id=request.user.id)

    if request.method == 'POST':
        # Get original User Form
        form = UserInfoForm(request.POST or None, instance=current_user)

        # Get User's Shipping Form
        shipping_form = ShippingForm(request.POST or None, instance=shipping_user)

        if form.is_valid() and shipping_form.is_valid():
            # Save original form
            form.save()

            # Save shipping form
            shipping_address = shipping_form.save(commit=False)

            # Use request.user instead of current_user (which is a Profile)
            shipping_address.user = request.user  # Changed from current_user to request.user
            shipping_address.save()

            messages.success(request, "Your Info Has Been Updated!!")
            return redirect('home')
    else:
        # Initialize forms with current data
        form = UserInfoForm(instance=current_user)
        shipping_form = ShippingForm(instance=shipping_user)

    return render(request, "update_info.html", {
        'form': form,
        'shipping_form': shipping_form,
        'user_profile': user_profile
    })

def search(request):
    # Determine if they filled out the form
    if request.method == "POST":
        searched = request.POST['searched']
        # Query The Products DB Model
        searched = Product.objects.filter(Q(name__icontains=searched) | Q(description__icontains=searched))
        # Test for null
        if not searched:
            messages.error(request, "That Product Does Not Exist...Please try Again.")
            return render(request, "search.html", {})
        else:
            return render(request, "search.html", {'searched': searched})
    else:
        return render(request, "search.html", {})